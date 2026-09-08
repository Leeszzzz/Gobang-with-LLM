from contextlib import asynccontextmanager
import aiosqlite
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
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
    return chess

@tool
def set_piece(row:int, col:int,runtime:ToolRuntime[LLMContext]):
    """
    下棋
    Args:
        row:行
        col:列
    return:
        下完当前棋后的棋盘
    """
    chess[row][col] = runtime.context.side
    return chess

@asynccontextmanager
async def lifespan(app: FastAPI):
    llm = init_chat_model("deepseek:deepseek-v4-flash")
    conn = await aiosqlite.connect("conversations.db")
    checkpoint = AsyncSqliteSaver(conn)
    agent = create_agent(
        model=llm,
        system_prompt="",
        checkpointer=checkpoint,
        tools=[get_chess_board,set_piece]
    )

    app.state.agent = agent
    app.state.checkpoint = checkpoint
    app.state.conn = conn
    yield


async def generate(chat_id,side):
    config = {
        "configurable": {
            "thread_id": str(chat_id)
        }
    }
    async for mode, data in app.state.agent.astream(
            {"messages": [HumanMessage(content="到你了")]},
            stream_mode=["messages", "updates"],
            context=LLMContext(chat_id=chat_id,side=side),
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


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/chat/")
def chat(chat_id,side):
    return StreamingResponse(
        generate(chat_id,side),
        media_type="text/event-stream",
    )

if __name__ == '__main__':
    print("\nServer: http://127.0.0.1:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
