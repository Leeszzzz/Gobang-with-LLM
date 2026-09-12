from contextlib import asynccontextmanager
import uvicorn
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel

# 行高 列宽
row = 13
col = 13
# row × col的棋盘
chess = [list(0 for _ in range(row)) for _ in range(col)]
# 此回合执棋方 1为黑棋 2为白棋
turn = 1


# 接口返回模型，也是大模型的上下文对象
class LLMContext(BaseModel):
    chat_id: int
    side: int


def check_chess(chess_board, latest_row, latest_col):
    """
    检查棋盘是否结束
    :param chess_board: 棋盘
    :param latest_row: 最后一次下棋位于的行数
    :param latest_col: 最后一次下棋位于的列数
    :return: 0代表未结束 1代表黑棋胜 2代表白棋胜
    """
    # 得到执棋方
    piece = chess_board[latest_row][latest_col]
    # 八向检测的四个方向向量
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    # 行高和列宽
    rows = len(chess_board)
    cols = len(chess_board[0])
    # 据四个向量进行循环
    for d_row, d_col in directions:
        # 记录当前下的棋子
        count = 1
        # 正向跳过当前棋子
        r, c = latest_row + d_row, latest_col + d_col
        while 0 <= r < rows and 0 <= c < cols and chess_board[r][c] == piece:
            # 在不在棋盘外并且正向下一步的棋子和执棋方一致的情况下，已连贯棋子+1，棋子位置正向移动
            count += 1
            r += d_row
            c += d_col
        # 反向跳过当前棋子
        r, c = latest_row - d_row, latest_col - d_col
        while 0 <= r < rows and 0 <= c < cols and chess_board[r][c] == piece:
            # 在不在棋盘外并且反向下一步的棋子和执棋方一致的情况下，已连贯棋子+1，棋子位置反向移动
            count += 1
            r -= d_row
            c -= d_col
        # 若连贯数到达5，游戏结束，返回执棋方
        if count >= 5:
            return piece
    # 游戏未结束
    return 0


@tool
def get_chess_board():
    """
    获取当前棋盘的棋子现状
    return
        棋盘
    """
    return {
        "type": "current_chess",
        "chess": chess
    }


@tool
def set_piece(row: int, col: int, runtime: ToolRuntime[LLMContext]):
    """
    下棋
    Args:
        row:行
        col:列
    return:
        下完当前棋后的棋盘
    """
    # 得到当前执棋方
    global turn
    # 判断当前回合是否为执棋方回合
    if turn != runtime.context.side:
        return {
            "type": "error",
            "content": "你已经下过棋了,现在不是你的回合,请结束请求"
        }
    # 要下的位置要为空
    if chess[row][col] == 0:
        # 下棋
        chess[row][col] = runtime.context.side
        # 转换回合
        turn = 3 - turn
        # 检查对局是否结束
        end = check_chess(chess, row, col)
        # 根据end结果返回相应类型
        return {
            "type": "end",
            "chess": chess
        } if end else {
            "type": "new_chess",
            "chess": chess
        }
    else:
        # 若要下的位置不为空
        return {
            "type": "error",
            "content": "此处已有棋子!"
        }


# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 配置模型
    llm = init_chat_model("deepseek:deepseek-v4-flash")
    # llm = ChatOpenAI(  # 本地模型测试
    #     base_url="http://localhost:6657/v1",
    #     api_key="machine",
    #     model="device",
    #     temperature=0.7,
    # )
    # 上下文记忆
    checkpoint = InMemorySaver()
    # 创建带有工具及上下文记忆的智能体
    agent = create_agent(
        model=llm,
        system_prompt="你正在下棋,棋盘中1为黑棋，2为白棋，0为空位置",
        checkpointer=checkpoint,
        tools=[get_chess_board, set_piece]
    )
    # 挂载到应用状态
    app.state.agent = agent
    app.state.checkpoint = checkpoint
    yield


async def generate(chat_id, side):
    """
    异步生成器函数，用来做sse流式相应
    :param chat_id: 会话的id
    :param side: 执棋方
    :yield: sse格式字符串
    """
    # 运行配置
    config = {
        "configurable": {
            "thread_id": str(chat_id) + "_" + str(side)
        }
    }
    # 混合模式输出运行智能体，并挂载运行配置和上下文记忆
    async for mode, data in app.state.agent.astream(
            {"messages": [HumanMessage(
                content=f"对手棋子已已下完,或你是先手,总之到你了,你是{"黑棋" if side == 1 else "白棋"},数组里表示{str(side)},请使用工具下棋")]},
            stream_mode=["messages", "updates"],
            context=LLMContext(chat_id=chat_id, side=side),
            config=config
    ):
        # 混合模式输出
        match mode:
            # messages模式，主要返回消息数据
            case "messages":
                # 获取消息块和元数据
                chunk, meta = data
                # 检查返回节点是否为模型，而不是工具等，不加这层判断会导致工具重复输出返回内容（虽然此项目不涉及工具返回内容）
                if chunk.content and meta.get("langgraph_node") == "model":
                    # 返回AI回复内容
                    yield f"event:content\ndata: {chunk.content}\n\n"
                # 若上面这个if判断chunk中没有内容就是模型在思考，返回思考内容
                reasoning_content = chunk.additional_kwargs.get("reasoning_content", "")
                # 返回思考内容
                if reasoning_content:
                    yield f"event:reasoning_content\ndata: {reasoning_content}\n\n"
            # updates模式，主要返回工具数据
            case "updates":
                # 解包元组得到键值
                for key, value in data.items():
                    for message in value["messages"]:
                        # 返回所调用工具名称
                        if hasattr(message, "tool_calls") and message.tool_calls:
                            yield f"event:tool_calls\ndata: {message.tool_calls[0]['name']}\n\n"
                        # 返回游戏未结束的信息和当前棋盘
                        if message.type == "tool" and json.loads(message.content).get("type") == "new_chess":
                            yield f"event:new_chess\ndata: {json.dumps(json.loads(message.content).get('chess'))}\n\n"
                        # 返回游戏结束的信息和当前棋盘
                        elif message.type == "tool" and json.loads(message.content).get("type") == "end":
                            yield f"event:end\ndata: {json.dumps(json.loads(message.content).get('chess'))}\n\n"


# 创建应用
app = FastAPI(lifespan=lifespan)
# 解决跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat")
def chat(req: LLMContext):
    """启动对话"""
    return StreamingResponse(
        generate(req.chat_id, req.side),
        media_type="text/event-stream",
    )


@app.get("/api/chess")
def get_chess():
    """得到当前棋盘"""
    return chess


if __name__ == '__main__':
    print("\nServer: http://127.0.0.1:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
