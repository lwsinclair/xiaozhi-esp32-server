import os
import uuid

import dashscope
from dashscope.audio.tts_v2 import *
from datetime import datetime
from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.model = config.get("model")
        self.voice = config.get("voice")

        dashscope.api_key = config.get("api_key")

    def generate_filename(self, extension=".mp3"):
        return os.path.join(self.output_file, f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}")

    async def text_to_speak(self, text, output_file):
        # 确保目录存在并创建空文件
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'wb') as f:
            pass

        synthesizer = SpeechSynthesizer(model=self.model, voice=self.voice)
        audio = synthesizer.call(text)
        print('[Metric] requestId: {}, first package delay ms: {}'.format(
            synthesizer.get_last_request_id(),
            synthesizer.get_first_package_delay()))

        with open(output_file, 'ab') as f:
            f.write(audio)

