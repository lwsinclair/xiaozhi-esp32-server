from config.logger import setup_logging
from config.settings import redisClient
from core.utils.util import check_model_key
from core.utils.util import invoking_http_api

TAG = __name__
logger = setup_logging()

TB_CACHE = {}


def append_devices_to_prompt(conn):
    if conn.use_function_call_mode:
        funcs = conn.config["Intent"]["function_call"].get("functions", [])
        if "tb_device" in funcs:

            prompt = "下面是我的智能设备，可以通过thingsboard控制\n"
            devices = conn.config["plugins"]["home_assistant"].get("devices", [])
            if len(devices) == 0:
                return
            for device in devices:
                prompt += device + "\n"
            conn.prompt += prompt
            """
            prompt内容：'下面是我家智能设备，可以通过thingsboard控制
            客厅,玩具灯,switch.cuco_cn_460494544_cp1_on_p_2_1
            卧室,台灯,switch.iot_cn_831898993_socn1_on_p_2_1
            '
            """
            # 更新提示词
            conn.dialogue.update_system_message(conn.prompt)
            init_tb_token(conn)


def initialize_tb_handler(conn):
    global TB_CACHE
    if TB_CACHE == {}:
        if conn.use_function_call_mode:
            funcs = conn.config["Intent"]["function_call"].get("functions", [])
            if "tb_device" in funcs:
                TB_CACHE['base_url'] = conn.config["plugins"]["home_assistant"].get("base_url")
                TB_CACHE['api_key'] = conn.config["plugins"]["home_assistant"].get("api_key")

                check_model_key("home_assistant", TB_CACHE['api_key'])
    return TB_CACHE

def init_tb_token(conn):
    device_id = conn.headers.get("device-id", "")
    key_prefix = "tb:"+device_id
    tb_token = redisClient.get(key_prefix+":token")
    if not tb_token:
        invoking_api = {
            "url": f"{redisClient.get('tb:url')}/api/auth/login",
            "method": "POST",
            "body": {
                "username": redisClient.get(key_prefix+":username"),
                "password": redisClient.get(key_prefix+":password")
            }
        }
        response_dict = invoking_http_api(invoking_api)
        redisClient.set(key_prefix+":token", response_dict["token"])
        redisClient.expire(key_prefix + ":token", 1800)
