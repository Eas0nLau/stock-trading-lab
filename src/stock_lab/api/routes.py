from fastapi import FastAPI


def register_routes(app: FastAPI) -> None:
    from 实时监控 import 情绪周期, 热门板块情绪, 策略选股, 资金流向

    资金流向.注册接口(app)
    策略选股.注册接口(app)
    情绪周期.注册接口(app)
    热门板块情绪.注册接口(app)
