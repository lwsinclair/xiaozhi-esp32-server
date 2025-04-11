from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions.hass_init import initialize_hass_handler
from config.logger import setup_logging
from config.settings import redisClient
import asyncio
import requests

TAG = __name__
logger = setup_logging()

tb_rpc_url = "/api/rpc/oneway/{deviceId}"

tb_device_function_desc = {
    "type": "function",
    "function": {
        "name": "tb_device",
        "description": "当用户想查询能控制哪些设备。",
        "parameters": {
            "type": "object",
            "properties": {
            },
            "required": []
        }
    }
}


@register_function('tb_device', tb_device_function_desc, ToolType.TB_CTL)
def tb_device(conn,function_name: str,param_dict: dict):
    try:
        future = asyncio.run_coroutine_threadsafe(
            handle_tb_device(conn,function_name,param_dict),
            conn.loop
        )
        ha_response = future.result()
        return ActionResponse(action=Action.REQLLM, result="执行成功", response=ha_response)
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理设置属性意图错误: {e}")


async def handle_tb_device(conn,function_name,param_dict):
    device_id = conn.headers.get("device-id", "00:11:22:33:44:55")
    tb_url = redisClient.get('tb:url')
    tb_token = redisClient.get('tb:token')

    if function_name == 'tb_device':
        pass

    description=""
    response=""
    if response.status_code == 200:
        return description
    else:
        return f"设置失败，错误码: {response.status_code}"
