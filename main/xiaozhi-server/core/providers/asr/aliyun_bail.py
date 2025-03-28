import io
import os
import time
import uuid
import wave
from typing import Optional, Tuple, List

import dashscope
import opuslib_next
from dashscope.audio.asr import *

from config.logger import setup_logging
from core.providers.asr.base import ASRProviderBase

TAG = __name__
logger = setup_logging()

class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        self.model = config.get("model")
        self.output_dir = config.get("output_dir")
        self.seg_duration = 12800

        dashscope.api_key = config.get("api_key")

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

    def save_audio_to_file(self, opus_data: List[bytes], session_id: str) -> str:
        """将Opus音频数据解码并保存为WAV文件"""
        file_name = f"asr_{session_id}_{uuid.uuid4()}.wav"
        file_path = os.path.join(self.output_dir, file_name)

        decoder = opuslib_next.Decoder(16000, 1)  # 16kHz, 单声道
        pcm_data = []

        for opus_packet in opus_data:
            try:
                pcm_frame = decoder.decode(opus_packet, 960)  # 960 samples = 60ms
                pcm_data.append(pcm_frame)
            except opuslib_next.OpusError as e:
                logger.bind(tag=TAG).error(f"Opus解码错误: {e}", exc_info=True)

        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 2 bytes = 16-bit
            wf.setframerate(16000)
            wf.writeframes(b"".join(pcm_data))

        return file_path

    async def _send_request(self, audio_data: List[bytes], segment_size: int) -> Optional[str]:
        """Send request to Aliyun ASR service."""
        try:
            # 设置 API Key

            # 创建回调对象
            callback = Callback()

            # 初始化翻译识别聊天对象
            translator = TranslationRecognizerChat(
                model=self.model,
                format="wav",
                sample_rate=16000,
                callback=callback,
            )
            translator.start()

            # 读取音频数据并分段发送
            audio_data_len = len(audio_data)
            offset = 0
            while offset < audio_data_len:
                chunk = audio_data[offset:offset + segment_size]
                if not translator.send_audio_frame(chunk):
                    print("sentence end, stop sending")
                    break
                offset += segment_size

            #logger.bind(tag=TAG).info("调用阿里云百炼语音识别前：")
            translator.stop()
            #logger.bind(tag=TAG).info("调用阿里云百炼语音识别后：")

            # 获取识别结果
            if callback.transcription_result is not None:
                return callback.transcription_result.text
            else:
                logger.bind(tag=TAG).info("XXXXX语音转换没有结果：callback.transcription_result is None")
                return None

        except Exception as e:
            logger.bind(tag=TAG).error(f"ASR request failed: {e}", exc_info=True)
            return None

    @staticmethod
    def decode_opus(opus_data: List[bytes], session_id: str) -> List[bytes]:

        decoder = opuslib_next.Decoder(16000, 1)  # 16kHz, 单声道
        pcm_data = []

        for opus_packet in opus_data:
            try:
                pcm_frame = decoder.decode(opus_packet, 960)  # 960 samples = 60ms
                pcm_data.append(pcm_frame)
            except opuslib_next.OpusError as e:
                logger.bind(tag=TAG).error(f"Opus解码错误: {e}", exc_info=True)

        return pcm_data

    @staticmethod
    def read_wav_info(data: io.BytesIO = None) -> (int, int, int, int, int):
        with io.BytesIO(data) as _f:
            wave_fp = wave.open(_f, 'rb')
            nchannels, sampwidth, framerate, nframes = wave_fp.getparams()[:4]
            wave_bytes = wave_fp.readframes(nframes)
        return nchannels, sampwidth, framerate, nframes, len(wave_bytes)

    @staticmethod
    def slice_data(data: bytes, chunk_size: int) -> (list, bool):
        """
        slice data
        :param data: wav data
        :param chunk_size: the segment size in one request
        :return: segment data, last flag
        """
        data_len = len(data)
        offset = 0
        while offset + chunk_size < data_len:
            yield data[offset: offset + chunk_size], False
            offset += chunk_size
        else:
            yield data[offset: data_len], True

    async def speech_to_text(self, opus_data: List[bytes], session_id: str) -> Tuple[Optional[str], Optional[str]]:
        """将语音数据转换为文本"""
        try:
            # 合并所有opus数据包
            pcm_data = self.decode_opus(opus_data, session_id)
            combined_pcm_data = b''.join(pcm_data)

            wav_buffer = io.BytesIO()

            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)  # 设置声道数
                wav_file.setsampwidth(2)  # 设置采样宽度
                wav_file.setframerate(16000)  # 设置采样率
                wav_file.writeframes(combined_pcm_data)  # 写入 PCM 数据

            # 获取封装后的 WAV 数据
            wav_data = wav_buffer.getvalue()
            nchannels, sampwidth, framerate, nframes, wav_len = self.read_wav_info(wav_data)
            size_per_sec = nchannels * sampwidth * framerate
            segment_size = int(size_per_sec * self.seg_duration / 1000)

            # 语音识别
            start_time = time.time()
            text = await self._send_request(wav_data, segment_size)
            if text:
                logger.bind(tag=TAG).debug(f"语音识别耗时: {time.time() - start_time:.3f}s | 结果: {text}")
                return text, None
            return "", None

        except Exception as e:
            logger.bind(tag=TAG).error(f"语音识别失败: {e}", exc_info=True)
            return "", None


class Callback(TranslationRecognizerCallback):
    def __init__(self):
        super().__init__()
        self.transcription_result = None

    def on_open(self) -> None:
        print("TranslationRecognizerCallback open.")

    def on_close(self) -> None:
        print("TranslationRecognizerCallback close.")

    def on_event(
            self,
            request_id,
            transcription_result: TranscriptionResult,
            translation_result: TranslationResult,
            usage,
    ) -> None:
        print("request id: ", request_id)
        print("usage: ", usage)
        if translation_result is not None:
            print(
                "translation_languages: ",
                translation_result.get_language_list(),
            )
            english_translation = translation_result.get_translation("en")
            print("sentence id: ", english_translation.sentence_id)
            print("translate to english: ", english_translation.text)
        if transcription_result is not None:
            print("sentence id: ", transcription_result.sentence_id)
            print("transcription: ", transcription_result.text)
            logger.bind(tag=TAG).info(f"阿里云百炼语音识别调用成功transcription_result.text successful - text: {transcription_result.text}")
            self.transcription_result = transcription_result

    def on_error(self, message) -> None:
        print('error: {}'.format(message))

    def on_complete(self) -> None:
        print('TranslationRecognizerCallback complete')