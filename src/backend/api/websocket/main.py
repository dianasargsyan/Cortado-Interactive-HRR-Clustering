from fastapi.routing import APIRouter
from typing import Callable
from starlette.websockets import WebSocket, WebSocketState, WebSocketDisconnect

from api.routes.conformance.variantConformance import (
    calculate_alignment_intern_with_timeout,
    get_alignment_callback,
)
from api.routes.variants.subvariantMining import (
    mine_repetition_patterns_with_timeout,
    RepetitionsMiningConfig,
    get_repetition_mining_callback,
)
from backend_utilities.configuration.repository import ConfigurationRepositoryFactory
from backend_utilities.multiprocessing.pool_factory import PoolFactory
from cache import cache
from endpoints.alignments import InfixType

router = APIRouter(tags=["websocket"], prefix="/ws")


class WebSocketService:
    def __init__(
        self, websocket: WebSocket, callback: Callable, timeout: int, name: str
    ):
        self.websocket = websocket
        self.callback = callback
        self.pool = PoolFactory.instance().get_pool()
        self.timeout = timeout
        self.name = name

    async def start_service(self):
        await self.websocket.accept()

        try:
            while True:
                data = await self.websocket.receive_json()

                if "isCancellationRequested" in data:
                    await self.websocket.close(1000)
                    PoolFactory.instance().restart_pool()
                    return

                try:
                    if "timeout" in data and data["timeout"] != 0:
                        self.timeout = data["timeout"]

                    await self.callback(data, self.timeout)

                except Exception as e:
                    if self.websocket.application_state == WebSocketState.CONNECTED:
                        await self.websocket.send_json({"error": str(e)})

        except WebSocketDisconnect as d:
            print(d)
            print("websocket disconnected")


class ConformanceWebsocketHandler(WebSocketService):
    def __init__(self, websocket: WebSocket, timeout: int):
        super().__init__(
            websocket, self.handle_message, timeout, "conformance checking"
        )

    async def handle_message(self, data, timeout: int):
        self.pool.apply_async(
            calculate_alignment_intern_with_timeout,
            (
                data["pt"],
                data["variant"],
                InfixType(data["infixType"]),
                timeout,
            ),
            callback=get_alignment_callback(
                data["id"], data["alignType"], self.websocket
            ),
        )


class ArcDiagramWebsocketHandler(WebSocketService):
    def __init__(self, websocket: WebSocket, timeout: int = None):
        super().__init__(websocket, self.handle_message, timeout, "arc diagrams")

    async def handle_message(self, data, timeout: int):
        self.pool.apply_async(
            mine_repetition_patterns_with_timeout,
            (
                RepetitionsMiningConfig(**data),
                cache.variants,
                cache.parameters["activites"],
                timeout,
            ),
            callback=get_repetition_mining_callback(self.websocket),
        )


@router.websocket("/conformance")
async def websocket_conformance(websocket: WebSocket):
    ws_handler = ConformanceWebsocketHandler(
        websocket,
        ConfigurationRepositoryFactory.get_config_repository()
        .get_configuration()
        .timeout_cvariant_alignment_computation,
    )
    await ws_handler.start_service()


@router.websocket("/repetitionsMining")
async def websocket_repetitions_mining(websocket: WebSocket):
    ws_handler = ArcDiagramWebsocketHandler(websocket)
    await ws_handler.start_service()
