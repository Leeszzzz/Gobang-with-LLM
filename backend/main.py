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
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel

row = 13
col = 13
chess = [list(0 for _ in range(row)) for _ in range(col)]


class LLMContext(BaseModel):
    chat_id: int
    side: int


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
    if chess[row][col] == 0:
        chess[row][col] = runtime.context.side
        return {
            "type": "new_chess",
            "chess": chess
        }
    else:
        return {
            "type": "error",
            "content": "此处已有棋子!"
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    llm = init_chat_model("deepseek:deepseek-v4-flash")
    checkpoint = InMemorySaver()
    agent = create_agent(
        model=llm,
        system_prompt="你正在下棋",
        checkpointer=checkpoint,
        tools=[get_chess_board, set_piece]
    )

    app.state.agent = agent
    app.state.checkpoint = checkpoint
    yield


async def generate(chat_id, side):
    config = {
        "configurable": {
            "thread_id": str(chat_id) + "_" + str(side)
        }
    }
    async for mode, data in app.state.agent.astream(
            {"messages": [HumanMessage(content="到你了")]},
            stream_mode=["messages", "updates"],
            context=LLMContext(chat_id=chat_id, side=side),
            config=config
    ):
        match mode:
            case "messages":
                chunk, meta = data
                if chunk.content and meta.get("langgraph_node") == "model":
                    yield f"event:content\ndata:{chunk.content}\n\n"
                reasoning_content = chunk.additional_kwargs.get("reasoning_content", "")
                if reasoning_content:
                    yield f"event:reasoning_content\ndata:{reasoning_content}\n\n"
            case "updates":
                for key, value in data.items():
                    for message in value["messages"]:
                        if hasattr(message, "tool_calls") and message.tool_calls:
                            yield f"event:tool_calls\ndata:{message.tool_calls[0]['name']}\n\n"
                        if message.type == "tool" and json.loads(message.content).get("type") == "new_chess":
                            yield f"event:new_chess\ndata:{json.dumps(json.loads(message.content).get('chess'))}\n\n"


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat")
def chat(req: LLMContext):
    return StreamingResponse(
        generate(req.chat_id, req.side),
        media_type="text/event-stream",
    )


@app.get("/api/chess")
def get_chess():
    return chess


if __name__ == '__main__':
    print("\nServer: http://127.0.0.1:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
