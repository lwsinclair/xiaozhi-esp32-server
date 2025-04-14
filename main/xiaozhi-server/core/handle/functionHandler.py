from config.logger import setup_logging
import json

from config.settings import redisClient
from plugins_func.register import FunctionRegistry, ActionResponse, Action, ToolType
from plugins_func.functions.tb_init import append_devices_to_prompt

TAG = __name__
logger = setup_logging()


class FunctionHandler:
    def __init__(self, conn):
        self.conn = conn
        self.config = conn.config
        self.function_registry = FunctionRegistry()
        self.register_nessary_functions()
        self.register_config_functions()
        self.functions_desc = self.function_registry.get_all_function_desc()
        func_names = self.current_support_functions()
        self.modify_plugin_loader_des(func_names)
        self.finish_init = True

    def modify_plugin_loader_des(self, func_names):
        if "plugin_loader" not in func_names:
            return
        # 可编辑的列表中去掉plugin_loader
        surport_plugins = [func for func in func_names if func != "plugin_loader"]
        func_names = ",".join(surport_plugins)
        for function_desc in self.functions_desc:
            if function_desc["function"]["name"] == "plugin_loader":
                function_desc["function"]["description"] = function_desc["function"][
                    "description"
                ].replace("[plugins]", func_names)
                break

    def upload_functions_desc(self):
        self.functions_desc = self.function_registry.get_all_function_desc()

    def current_support_functions(self):
        func_names = []
        for func in self.functions_desc:
            func_names.append(func["function"]["name"])
        # 打印当前支持的函数列表
        logger.bind(tag=TAG).info(f"当前支持的函数列表: {func_names}")
        return func_names

    def get_functions(self):
        """获取功能调用配置"""
        return self.functions_desc

    def register_nessary_functions(self):
        """注册必要的函数"""
        self.function_registry.register_function("handle_exit_intent")
        self.function_registry.register_function("plugin_loader")
        self.function_registry.register_function("get_time")
        self.function_registry.register_function("get_lunar")
        self.function_registry.register_function("handle_device")

    def register_config_functions(self):
        """注册配置中的函数,可以不同客户端使用不同的配置"""
        for func in self.config["Intent"][self.config["selected_module"]["Intent"]].get(
            "functions", []
        ):
            self.function_registry.register_function(func)


        """tb系统需要初始化提示词"""
        if self.function_registry.function_registry.get("tb_device"):
            tb_device_list = append_devices_to_prompt(self.conn)
            #添加tb系统函数-qiu
            if tb_device_list:

                all_devices = redisClient.lrange('tb:device', 0, -1)
                device_type_dict = {}
                # 遍历每个元素，解析 JSON 并构建结果字典
                for item in all_devices:
                    try:
                        # 将 JSON 字符串反序列化为 Python 字典
                        data = json.loads(item)
                        # 检查字典中是否包含所需的键
                        if 'type' in data and 'funs' in data:
                            # 使用 'type' 作为键，'funs' 作为值
                            device_type_dict[data['type']] = data['funs']
                    except json.JSONDecodeError:
                        print(f"无法解析 JSON: {item}")

                # 初始化功能字典
                func_dict = {}
                tb_names = {e["name"] for e in tb_device_list}
                tb_name_fun = {
                    "type": "list",
                    "description": redisClient.get('tb:name_desc').format(names=tb_names)
                }
                # 遍历设备列表，直接构造功能字典
                for device in tb_device_list:
                    device_type = device.get("type")
                    tb_names.add(device["name"])
                    if device_type and device_type in device_type_dict:
                        tb_funs = device_type_dict[device_type]
                        for fun_name in tb_funs:
                            function_call = json.loads(redisClient.hget(f"tb:device_fun:{device_type}:{fun_name}", "function_call"))
                            properties = function_call["function"]["parameters"]["properties"]
                            properties["tb_name"] = tb_name_fun
                            func_dict[device_type+"_"+fun_name] = function_call


                # 遍历功能字典，注册功能
                for tb_key,tb_value in func_dict.items():
                    self.function_registry.register_tb_function(tb_key,tb_value)


    def get_function(self, name):
        return self.function_registry.get_function(name)

    def handle_llm_function_call(self, conn, function_call_data):
        try:
            function_name = function_call_data["name"]
            funcItem = self.get_function(function_name)
            if not funcItem:
                return ActionResponse(
                    action=Action.NOTFOUND, result="没有找到对应的函数", response=""
                )
            func = funcItem.func
            arguments = function_call_data["arguments"]
            arguments = json.loads(arguments) if arguments else {}
            logger.bind(tag=TAG).info(f"调用函数: {function_name}, 参数: {arguments}")
            if (
                funcItem.type == ToolType.SYSTEM_CTL
                or funcItem.type == ToolType.IOT_CTL
            ):
                return func(conn, **arguments)
            elif funcItem.type == ToolType.WAIT:
                return func(**arguments)
            elif funcItem.type == ToolType.CHANGE_SYS_PROMPT:
                return func(conn, **arguments)
            elif funcItem.type == ToolType.TB_CTL:
                #增加执行方法处理-qiu
                return func(conn,function_name, arguments)
            else:
                return ActionResponse(
                    action=Action.NOTFOUND, result="没有找到对应的函数", response=""
                )
        except Exception as e:
            logger.bind(tag=TAG).error(f"处理function call错误: {e}")

        return None
