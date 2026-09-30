from contextlib import asynccontextmanager
import uvicorn
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_deepseek import ChatDeepSeek
from langchain_openai import OpenAIEmbeddings
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


def create_agent_black(base_url, api_key, model):
    llm = ChatDeepSeek(
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
    agent = create_agent(
        model=llm,
        system_prompt="你正在下棋,棋盘中1为黑棋，2为白棋，0为空位置",
        checkpointer=app.state.checkpoint,
        tools=[get_chess_board, set_piece_tool, search_doc]
    )
    return agent


def create_agent_white(base_url, api_key, model):
    llm = ChatDeepSeek(
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
    agent = create_agent(
        model=llm,
        system_prompt="你正在下棋,棋盘中1为黑棋，2为白棋，0为空位置",
        checkpointer=app.state.checkpoint,
        tools=[get_chess_board, set_piece_tool, search_doc]
    )
    return agent


# 接口返回模型，也是大模型的上下文对象
class LLMContext(BaseModel):
    chat_id: int
    side: int


class LLMConfig(BaseModel):
    base_url: str
    api_key: str
    model: str


class HumanChess(BaseModel):
    side: int
    row: int
    col: int


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
def set_piece_tool(row: int, col: int, runtime: ToolRuntime[LLMContext]):
    """
    下棋
    Args:
        row:行
        col:列
    return:
        下完当前棋后的棋盘
    """
    return set_piece(row, col, runtime.context.side)


@tool
def search_doc(query: str):
    """
    RAG相似检索查询五子棋技巧等信息
    Args:
         query:查询内容
    return:
        相似度检索后的文本
    """
    docs = app.state.retriever.invoke(query)
    results = [doc.page_content for doc in docs]
    return {
        "type":"search_results",
        "content":results
    }


def set_piece(row: int, col: int, side: int):
    # 得到当前执棋方
    global turn
    # 判断当前回合是否为执棋方回合
    if turn != side:
        return {
            "type": "error",
            "content": "你已经下过棋了,现在不是你的回合,请结束请求"
        }
    # 要下的位置要为空
    if chess[row][col] == 0:
        # 下棋
        chess[row][col] = side
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
    checkpoint = InMemorySaver()

    # 本地embedding模型
    embeddings = OpenAIEmbeddings(
        model="qwen-3-embedding",
        base_url="http://localhost:6658/v1",
        api_key="key",
        check_embedding_ctx_length=False,
        chunk_size=10
    )

    vector_store = InMemoryVectorStore(
        embedding=embeddings
    )

    #限阶段测试，后续会支持外部文件导入和切块
    vector_store.add_texts(
        [
            "五子棋使用n×n棋盘，黑先白后，横、竖、斜任意方向先连成五子者胜。连珠规则中黑棋有禁手：双三、双四、长连；白棋无禁手，可抓黑棋禁手取胜。",
            "黑棋禁手包括双三、双四和长连。双三是一手同时形成两个活三；双四是一手同时形成两个四；长连是连成六子及以上。黑棋走禁手判负，白棋可故意制造禁手局面。",
            "白棋无禁手，核心战术之一是抓禁手。通过做双三、双四、长连威胁，迫使黑棋只能下在禁手点，或让黑棋防守时形成禁手。",
            "活二是两子相连且两端有发展空间的棋形，如 _XX_。活二可发展为活三，是进攻的基础。优先保留和制造多个活二，形成连接。",
            "眠二是一端被堵或发展空间不足的二，如 OXX_ 或 _XXO。眠二价值低于活二，通常用于辅助连接或做棋，不宜作为主攻方向。",
            "活三是三子相连或跳连，两端有空，下一手可成活四，如 _XXX_、_X_XX_。对方形成活三时必须应对，否则会变成活四。",
            "眠三是一端被堵或只能单向延伸的三，如 OXXX_。眠三下一手只能冲四，对方必须挡，但本身不能直接成活四，价值低于活三。",
            "冲四是四子一端被堵，下一手在空端成五，如 OXXXX_。冲四必须挡。连续冲四可以迫使对方防守，是VCF的基础。",
            "活四是四子两端都有空，如 _XXXX_。下一手在任一端都能成五，对方无法同时防守，因此活四基本等于胜势。",
            "双三是一手同时形成两个活三。对方无法同时防守两个活三，通常必胜。黑棋双三为禁手，白棋双三是重要取胜手段。",
            "四三是一手同时形成四和活三，例如冲四加活三。对方必须挡四，随后活三变成活四，通常可胜。四三是常见胜法。",
            "双四是一手同时形成两个四，包括两个冲四或冲四加活四。对方只能挡一个四，另一个成五。黑棋双四为禁手。",
            "VCF 是连续冲四取胜（Victory by Continuous Fours）。通过不断冲四，迫使对方连续防守，最终形成五连。计算时优先寻找VCF线路。",
            "VCT 是连续活三取胜（Victory by Continuous Threats）。通过活三、冲四、做杀等连续威胁，让对方始终处于防守，最终取胜。",
            "做棋是不直接形成三或四，而是制造后续多重威胁。例如做双二、做眠三、做活三、做四三。好的做棋能让对方难以兼顾。",
            "防守优先级：对方冲四必须挡；对方活三必须挡；对方双三、四三要提前破坏；对方做棋要抢占要点。防守时不要只看当前，要算后续连接。",
            "五子棋中心价值最高。黑棋第一手通常下天元。开局应尽量靠近中心，保持多方向连接，避免过早下在边角。",
            "白棋第二手与黑棋成直线相邻称为直指，成斜线相邻称为斜指。直指和斜指会导向不同开局体系，如浦月、花月、寒星、溪月等。",
            "常见开局有浦月、花月、寒星、溪月、疏星、斜月、长星、瑞星、明星、岚月等。黑棋要利用先手，白棋要平衡并寻找抓禁手机会。",
            "八卦阵是白棋常用防守阵型，棋子按马步（日字）分布，形成相互呼应、限制黑棋连线的结构。可有效降低黑棋进攻效率并诱导禁手。",
            "梅花阵是围绕中心形成多点开花的进攻结构，强调多个活二、活三相互连接。核心是保持先手，制造双三、四三等复合威胁。",
            "选点优先考虑连接多、方向多、空间大的位置。一个点能同时连接多个棋形时价值高。边缘和死角空间小，价值低。",
            "先手是迫使对方必须应对的棋。进攻时要保持先手，连续制造冲四、活三；防守时要争夺先手，不能一直被动挨打。",
            "计算顺序：先看对方是否有冲四、活三、VCF；再看自己是否有VCF、VCT；然后比较做棋和防守点。进攻前先确认对方没有反杀。",
            "口诀：连二做三，连三做四，连四成五；三三、四四、四三；黑怕禁手，白抓禁手；有冲先冲，无冲做棋；攻不忘守，守中带攻。",
            "常见错误：只攻不守、忽略对方冲四、忘记黑棋禁手、盲目冲四浪费材料、活三被反杀、做棋不连接。复盘时重点检查这些点。",
            "训练方法：做VCF/VCT题、死活题、开局定式、复盘实战。先练计算冲四和活三，再练做棋和禁手判断，最后练全局攻防。",
        ]
    )

    retriever = vector_store.as_retriever(
        search_type="similarity",
        # 默认返回三条结果
        search_kwargs={"k": 3}
    )

    app.state.checkpoint = checkpoint
    app.state.retriever = retriever

    print("lifespan初始化完成")

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
    agent = app.state.agent_black if side == 1 else app.state.agent_white
    # 混合模式输出运行智能体，并挂载运行配置和上下文记忆
    async for mode, data in agent.astream(
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
    if hasattr(app.state, "agent_black") and hasattr(app.state, "agent_white"):
        return StreamingResponse(
            generate(req.chat_id, req.side),
            media_type="text/event-stream",
        )
    else:
        return {
            "type": "error",
            "content": "双方模型未初始化"
        }


@app.get("/api/chess")
def get_chess():
    """得到当前棋盘"""
    return chess


@app.post("/api/create_black")
def create_black(req: LLMConfig):
    """初始化黑棋智能体"""
    agent = create_agent_black(req.base_url, req.api_key, req.model)
    app.state.agent_black = agent
    return {
        "type": "success",
        "content": "黑棋初始化完成"
    }


@app.post("/api/create_white")
def create_white(req: LLMConfig):
    """初始化白棋智能体"""
    agent = create_agent_white(req.base_url, req.api_key, req.model)
    app.state.agent_white = agent
    return {
        "type": "success",
        "content": "白棋初始化完成"
    }


@app.post("/api/set_chess")
def set_chess(req: HumanChess):
    """人类方下棋"""
    return set_piece(req.row, req.col, req.side)


if __name__ == '__main__':
    print("\nServer: http://127.0.0.1:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
