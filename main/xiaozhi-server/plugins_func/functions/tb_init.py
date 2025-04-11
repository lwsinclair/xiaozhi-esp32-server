import json
from config.logger import setup_logging
from config.settings import redisClient
from core.utils.util import check_model_key
from core.utils.util import invoking_http_api

TAG = __name__
logger = setup_logging()

TB_CACHE = {}

userUrl = "api/auth/user"
loginUrl = "api/auth/login"
getCustomerDeviceInfos = "api/customer/{customer_id}/deviceInfos"


def append_devices_to_prompt(conn):
    device_id = conn.headers.get("device-id", "00:11:22:33:44:55")
    if device_id and conn.use_function_call_mode:
        init_tb_token(device_id) #初始化token
        tbuser = getTbUser(device_id)
        customer_id = tbuser["customerId"]["id"]
        tb_device_list = getTbDevices(device_id,customer_id)

        prompt = "下面是我的设备，可以通过小智控制\n"
        if len(tb_device_list) == 0:
            return

        control_device_dict = {}
        for tb_device in tb_device_list:
            control_device_list = control_device_dict.get(tb_device["type"], [])
            control_device_list.append(tb_device)
            control_device_dict[tb_device["type"]] = control_device_list

        # 序列化字典中的列表为 JSON 字符串
        control_device_dict_serialized = {k: json.dumps(v) for k, v in control_device_dict.items()}
        redisClient.hmset(f"tb:{device_id}:control_device",control_device_dict_serialized)

        for tb_device in tb_device_list:
            prompt += tb_device["name"] + "\n"
        conn.prompt += prompt
        """
        "," + tb_device["id"]["id"] + 
        
        prompt内容：'下面是我家智能设备，可以通过thingsboard控制
        客厅,玩具灯,switch.cuco_cn_460494544_cp1_on_p_2_1
        卧室,台灯,switch.iot_cn_831898993_socn1_on_p_2_1
        '
        """
        # 更新提示词
        conn.dialogue.update_system_message(conn.prompt)

        return tb_device_list



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

#初始化tb系统token缓存
def init_tb_token(device_id):
    if device_id:
        key_prefix = "tb:"+device_id
        tb_token = redisClient.get(key_prefix+":token")
        if not tb_token:
            invoking_api = {
                "url": f"{redisClient.get('tb:url')}/{loginUrl}",
                "method": "POST",
                "body": {
                    "username": redisClient.get(key_prefix+":username"),
                    "password": redisClient.get(key_prefix+":password")
                }
            }
            response_dict = invoking_http_api(invoking_api)
            redisClient.set(key_prefix+":token", response_dict["token"])
            redisClient.expire(key_prefix + ":token", 1800)

#获取tb用户
def getTbUser(device_id):
    key_prefix = "tb:"+device_id
    invoking_api = {
        "url": f"{redisClient.get('tb:url')}/{userUrl}",
        "headers": {
            "Authorization": "Bearer "+redisClient.get(key_prefix+":token")
        }
    }
    return invoking_http_api(invoking_api)

#获取tb设备
def getTbDevices(device_id,customer_id,**kwargs):
    key_prefix = "tb:"+device_id
    url = f"{redisClient.get('tb:url')}/{getCustomerDeviceInfos}?active=true&page=0&pageSize=50"
    url = url.format(customer_id=customer_id)
    for key,value in kwargs.items():
        url += "&"+key+"="+value

    invoking_api = {
        "url": url,
        "headers": {
            "Authorization": "Bearer "+redisClient.get(key_prefix+":token")
        }
    }
    return invoking_http_api(invoking_api)["data"]