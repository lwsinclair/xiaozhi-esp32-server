import asyncio
import json

from config.logger import setup_logging
from config.settings import redisClient
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.utils.util import invoking_http_api
from plugins_func.functions.tb_init import init_tb_token

TAG = __name__
logger = setup_logging()
tb_fun = "tb_device"

tb_rpc_url = "/api/rpc/oneway/{deviceId}"

tb_device_function_desc = {
    "type": "function",
    "function": {
        "name": "tb_device",
        "description": "用于查询当前用户可控制的设备列表，不涉及设备操作,只用于当用户要明确查询能够控制哪些设备时才触发。",
        "parameters": {
            "type": "object",
            "properties": {
            },
            "required": [],
            "description": "此函数不接受参数，仅返回用户可控制的设备列表。"
        }
    }
}

tb_name = {
    "type": "string",
    "description": "需要操作设备的名称,只在set列表里匹配返回对应的名称,匹配不到不返回"
}



@register_function("tb_device", tb_device_function_desc, ToolType.TB_CTL)
def tb_device(conn,function_name: str,param_dict: dict):
    try:
        future = asyncio.run_coroutine_threadsafe(
            handle_tb_device(conn,function_name,param_dict),
            conn.loop
        )
        return future.result()
    except Exception as e:
        logger.bind(tag=TAG).error(f"处理设置属性意图错误: {e}")


async def handle_tb_device(conn,function_name,param_dict):
    device_id = conn.headers.get("device-id", "00:11:22:33:44:55")
    tb_url = redisClient.get('tb:url')
    tb_token = init_tb_token(device_id)
    control_device_dict = redisClient.hgetall(f"tb:{device_id}:control_device")
    action_response = ActionResponse(action=Action.REQLLM, result="执行成功", response=None)
    description = ""
    if function_name == tb_fun:
        description = "小智能为您控制的智能设备为："
        if control_device_dict:
            device_set = set()
            for tb_key,tb_value in control_device_dict.items():
                for tb_view in json.loads(tb_value):
                    device_set.add(tb_view["name"])

            for tb_name in device_set:
                description += tb_name + ","
        else:
            description = "您的账号下没有能控制的智能设备"

        action_response.action = Action.RESPONSE

    else:
        sre_parse = function_name.split("_")
        device_views = json.loads(control_device_dict.get(sre_parse[0]))
        fun_key = f"tb:device_fun:{function_name.replace('_',':')}"
        method = redisClient.hget(fun_key,"method")
        if len(device_views) == 1:
            tb_deviceId = device_views[0]["id"]["id"]
            invoking_api = {
                "url": tb_url + tb_rpc_url.format(deviceId=tb_deviceId),
                "method": "POST",
                "headers": {
                    "Authorization": "Bearer "+tb_token
                },
                "body": {
                    "method": method,
                    "params": param_dict,
                    "persistent": False,
                    "timeout": 5000
                }
            }
            response = invoking_http_api(invoking_api)
            if response.status_code != 200:
                description = f"设置失败，错误码: {response.status_code}"
            else:
                pass
        else:
            names = ""
            for device_view in device_views:
                names += device_view["name"] + ","
            description = f"小智为您匹配到{len(device_views)}台设备,分别为{names}您要控制的是那一台？"
            action_response.action = Action.RESPONSE

    action_response.response = description
    action_response.result = description

    return action_response
