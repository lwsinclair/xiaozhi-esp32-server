from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions.hass_init import initialize_hass_handler
from config.logger import setup_logging
from config.settings import redisClient
import asyncio
import requests

TAG = __name__
logger = setup_logging()

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
    device_id = conn.headers.get("device-id", "")
    tb_url = redisClient.get('tb:url')
    tb_token = redisClient.get('tb:token')
    entity_id = ""
    HASS_CACHE = initialize_hass_handler(conn)
    api_key = HASS_CACHE['api_key']
    base_url = HASS_CACHE['base_url']
    '''
    state = { "type":"brightness_up","input":"80","is_muted":"true"}
    '''
    domains = entity_id.split(".")
    if len(domains) > 1:
        domain = domains[0]
    else:
        return "执行失败，错误的设备id"
    action = ''
    arg = ''
    value = ''
    if param_dict['type'] == 'turn_on':
        description = "设备已打开"
        if domain == "cover":
            action = "open_cover"
        elif domain == "vacuum":
            action = "start"
        else:
            action = "turn_on"
    else:
        return f"{domain} {param_dict.type}功能尚未支持"

    if arg == '':
        data = {
            "entity_id": entity_id,
        }
    else:
        data = {
            "entity_id": entity_id,
            arg: value
        }
    url = f"{base_url}/api/services/{domain}/{action}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json=data)
    logger.bind(tag=TAG).info(f"设置状态:url:{url},return_code:{response.status_code}")
    if response.status_code == 200:
        return description
    else:
        return f"设置失败，错误码: {response.status_code}"
