import json

from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions.hass_init import initialize_hass_handler
from config.logger import setup_logging
from config.settings import redisClient
import asyncio
import requests

TAG = __name__
logger = setup_logging()
tb_fun = "tb_device"

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


@register_function("tb_device", tb_device_function_desc, ToolType.TB_CTL)
def tb_device(conn,function_name: str,param_dict: dict):
    try:
        future = asyncio.run_coroutine_threadsafe(
            handle_tb_device(conn,function_name,param_dict),
            conn.loop
        )
        ha_response = future.result()
        action_response = ActionResponse(action=Action.REQLLM, result="执行成功", response=ha_response)
        if function_name == tb_fun:
            action_response.action = Action.RESPONSE
            #action_response.result = ha_response
            action_response.response = ha_response
        return action_response
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理设置属性意图错误: {e}")


async def handle_tb_device(conn,function_name,param_dict):
    device_id = conn.headers.get("device-id", "00:11:22:33:44:55")
    tb_url = redisClient.get('tb:url')
    tb_token = redisClient.get('tb:token')
    control_device_dict = redisClient.hgetall(f"tb:{device_id}:control_device")
    description = ""
    if function_name == tb_fun:
        description = "能控制的智能设备为："
        if control_device_dict:
            device_set = set()
            for tb_key,tb_value in control_device_dict.items():
                #self.function_registry.register_tb_function(tb_key,json.loads(tb_value))
                for tb_view in json.loads(tb_value):
                    device_set.add(tb_view["name"])

            for tb_name in device_set:
                description += tb_name + ","
        else:
            description = "您的账号下没有能控制的智能设备"

    response=""
    if description:
        return description
    else:
        return f"设置失败，错误码: {response.status_code}"
