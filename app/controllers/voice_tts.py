import edge_tts
import tornado.web


class VoiceTTSHandler(tornado.web.RequestHandler):

    def check_xsrf_cookie(self):
        pass

    async def post(self):
        text = (self.get_body_argument("text", "") or "").strip()
        if not text:
            self.set_status(400)
            self.finish({"error": "text is required"})
            return

        voice = self.get_body_argument("voice", "zh-CN-XiaoxiaoNeural")
        rate = self.get_body_argument("rate", "+0%")

        communicate = edge_tts.Communicate(text, voice, rate=rate)

        self.set_header("Content-Type", "audio/mpeg")
        self.set_header("Cache-Control", "no-cache")

        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        self.write(audio_data)
        self.finish()
