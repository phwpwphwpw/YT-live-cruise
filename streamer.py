# streamer.py (v1.2 - 健壮路径版)
import subprocess
import time
import json
import os
import sys
import threading
from configobj import ConfigObj
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, UTC

# ---【路径修正：第一部分】---
# 获取 streamer.py 自身的绝对目录
script_dir = os.path.dirname(os.path.abspath(__file__))
# ---【修正结束】---

# --- 【核心修正】 ---
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 从同级目录导入抓流模组
import douyin

class Streamer:
    def __init__(self, profile_path: str):
        self.profile_path = profile_path
        self.config_filepath = os.path.join(profile_path, 'config.ini')
        self.stream_info_path = os.path.join(profile_path, 'stream_info.json')
        
        try:
            self.config = ConfigObj(self.config_filepath, encoding='UTF8')
        except Exception as e:
            self.log_message('ERROR', f"无法加载设定档 {self.config_filepath}: {e}")
            sys.exit(1)

        self.ffmpeg_process = None
        self.is_running = True
        self.current_broadcast_id = None
        self.douyin_id = self.config.get('Douyin', {}).get('douyin_id', os.path.basename(profile_path))

    def log_message(self, level: str, message: str):
        print(f"LOG:{level.upper()}:{message}")
        sys.stdout.flush()

    def set_status(self, status: str):
        print(f"STATUS:{status}")
        sys.stdout.flush()
        
    def send_title(self, title: str):
        print(f"TITLE:{title}")
        sys.stdout.flush()

    def run(self):
        try:
            self.log_message("INFO", f"后台转播程序已为 {self.douyin_id} 启动。")
            self.set_status("starting")
            if not self._preflight_check():
                raise Exception("启动前环境检测失败。")
            self._main_loop()
        except Exception as e:
            self.set_status("error")
            self.log_message("ERROR", f"程序遇到致命错误: {e}")
        finally:
            self.cleanup()

    def _main_loop(self):
        youtube = self._get_authenticated_service()
        if not youtube:
            raise Exception("无法获取 YouTube 认证服务。")

        stream_id, youtube_key = self._get_or_create_stream_and_key(youtube, self.douyin_id)
        
        self.log_message("INFO", "启动抖音 → YouTube 自动转播系统")
        pushing = False
        check_interval = int(self.config.get('Douyin', {}).get('check_interval', 60))
        
        while self.is_running:
            if not pushing:
                self.set_status("checking")
                self.log_message("INFO", "主播未开播或推流中断，进入检查模式...")
                
                chrome_path = self.config.get('System', {}).get('chrome_path')
                proxy_url = self.config.get('Proxy', {}).get('proxy_url')
                wait_time = int(self.config.get('Douyin', {}).get('wait_time', 30))
                proxy_config = {"server": proxy_url} if proxy_url else {}

                flv_url, title = douyin.get_stream_info(self.douyin_id, chrome_path, proxy_config, wait_time)

                if flv_url:
                    if title: self.send_title(title)
                    self.log_message("INFO", "🎯 检测到主播开播，准备推流...")
                    try:
                        self.current_broadcast_id = self._create_live_broadcast(youtube)
                        self._bind_stream(youtube, self.current_broadcast_id, stream_id)
                        self.ffmpeg_process = self._start_ffmpeg_stream(flv_url, youtube_key)
                        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
                            self.set_status("streaming"); pushing = True
                            self.log_message("INFO", "✅ 推流进程已启动，进入巡航模式。")
                        else:
                            self.log_message("ERROR", "❌ 推流启动失败，将在下一轮检测时重试。")
                            self.set_status("error")
                    except Exception as e:
                        self.log_message("ERROR", f"❌ 创建或推流时发生异常：{e}")
                        self.set_status("error")
                else:
                    self.set_status("offline")
                    self.log_message("INFO", f"🌙 主播未开播，将在 {check_interval} 秒后再次检查。")
            else:
                if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
                    self.set_status("streaming")
                    self.log_message("INFO", "✅ 推流正在进行中...")
                else:
                    self.log_message("WARN", "⚠️ 检测到推流进程已停止！返回检查模式。")
                    self.set_status("checking")
                    pushing = False
            
            for _ in range(check_interval):
                if not self.is_running: break
                time.sleep(1)

    def cleanup(self):
        self.is_running = False
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            self.log_message("INFO", "🔪 正在停止残留的推流进程...")
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log_message("WARN", "FFmpeg 进程在5秒内未终止，强制结束。")
                self.ffmpeg_process.kill()
        self.log_message("INFO", "⛔️ 转播任务已停止。")
        self.set_status("stopped")
        
    def _preflight_check(self):
        self.log_message("INFO", "🩺 正在执行启动前环境检测...")
        ffmpeg_path = self.config.get('FFmpeg', {}).get('ffmpeg_path', 'ffmpeg')
        try:
            result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, check=True, encoding='utf-8', errors='ignore')
            self.log_message("INFO", "✅ FFmpeg 环境检测通过！")
            return True
        except FileNotFoundError:
            self.log_message("ERROR", f"❌ FFmpeg 环境检测失败: 找不到 '{ffmpeg_path}'。请检查 FFmpeg 路径设定或系统环境变数。")
            return False
        except Exception as e:
            self.log_message("ERROR", f"❌ FFmpeg 环境检测失败: {e}")
            return False

    def _get_authenticated_service(self):
        scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        token_filename = self.config.get('YouTube', {}).get('token_file', 'token.json')
        
        # ---【路径修正：第二部分】---
        # 根据 streamer.py 自身的位置，来定位 credentials 资料夹
        credentials_dir = os.path.join(script_dir, 'credentials')
        token_path = os.path.join(credentials_dir, token_filename)
        # ---【修正结束】---

        if not os.path.exists(token_path):
            self.log_message("ERROR", f"凭证档案 '{token_path}' 不存在。请在主控台为此主播设定正确的凭证。")
            return None
        try:
            creds = Credentials.from_authorized_user_file(token_path, scopes)
            return build("youtube", "v3", credentials=creds)
        except Exception as e:
            self.log_message("ERROR", f"❌ YouTube API 认证失败: {e}")
            return None

    def _get_or_create_stream_and_key(self, youtube, dy_id):
        # (此函数内的路径 self.stream_info_path 依赖于从 manager 传来的 profile_path，是正确的，无需修改)
        if os.path.exists(self.stream_info_path):
            with open(self.stream_info_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.log_message("INFO", f"已从 {self.stream_info_path} 加载现有推流码。")
            return data['stream_id'], data['youtube_key']
        
        self.log_message("INFO", "ℹ️ 正在为此主播创建新的 YouTube 固定推流码...")
        request = youtube.liveStreams().insert(part="snippet,cdn,contentDetails", body={
            "snippet": {"title": f"固定推流码-{dy_id}"},
            "cdn": {"frameRate": "variable", "ingestionType": "rtmp", "resolution": "variable"},
            "contentDetails": {"isReusable": True}
        })
        response = request.execute()
        stream_id, youtube_key = response["id"], response["cdn"]["ingestionInfo"]["streamName"]
        with open(self.stream_info_path, "w", encoding="utf-8") as f:
            json.dump({"stream_id": stream_id, "youtube_key": youtube_key}, f, ensure_ascii=False, indent=2)
        self.log_message("INFO", f"🎉 成功创建并保存了新的推流码信息到 {self.stream_info_path}。")
        return stream_id, youtube_key
    
    def _create_live_broadcast(self, youtube):
        yt_config = self.config.get('YouTube', {})
        self.log_message("INFO", "ℹ️ 正在创建 YouTube 直播间...")
        body = {
            "snippet": { "title": yt_config.get('broadcast_title', f'转播 - {self.douyin_id}'), "description": yt_config.get('broadcast_description', ''), "scheduledStartTime": datetime.now(UTC).isoformat()},
            "status": { "privacyStatus": yt_config.get('privacy_status', 'private'),"selfDeclaredMadeForKids": False },
            "contentDetails": { "enableAutoStart": str(yt_config.get('enable_auto_start', 'true')).lower() == 'true', "enableAutoStop": str(yt_config.get('enable_auto_stop', 'true')).lower() == 'true', "enableDvr": str(yt_config.get('enable_dvr', 'true')).lower() == 'true', "recordFromStart": str(yt_config.get('record_from_start', 'true')).lower() == 'true'}
        }
        if yt_config.get('category_id'): body['snippet']['categoryId'] = yt_config.get('category_id')
        response = youtube.liveBroadcasts().insert(part="snippet,contentDetails,status", body=body).execute()
        self.log_message("INFO", f"✅ 直播间创建成功，ID: {response['id']}")
        return response["id"]

    def _bind_stream(self, youtube, broadcast_id, stream_id):
        self.log_message("INFO", f"正在绑定直播间 (ID: {broadcast_id}) 与推流码 (ID: {stream_id})")
        youtube.liveBroadcasts().bind(part="id,contentDetails", id=broadcast_id, streamId=stream_id).execute()
        self.log_message("INFO", f"🔗 已成功绑定直播间与推流码。")
        
    def _start_ffmpeg_stream(self, flv_url, youtube_key):
        rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{youtube_key}"
        ffmpeg_config = self.config.get('FFmpeg', {}); ffmpeg_path = ffmpeg_config.get('ffmpeg_path', 'ffmpeg'); bitrate = ffmpeg_config.get('bitrate', '4000k')
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        headers = f"Referer: https://live.douyin.com/\r\nUser-Agent: {user_agent}\r\n"
        cmd = [ffmpeg_path, "-re", "-headers", headers, "-i", flv_url, "-c:v", "copy", "-c:a", "aac", "-ar", "44100", "-b:v", bitrate, "-f", "flv", rtmp_url]
        self.log_message("INFO", f"🚀 正在启动 FFmpeg 推流... (模式: 直接複製视讯流)")
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='ignore', creationflags=creationflags)
            threading.Thread(target=self._log_ffmpeg_output, args=(process,), daemon=True).start()
            time.sleep(5)
            if process.poll() is None:
                self.log_message("INFO", f"✅ FFmpeg 进程已成功启动 (PID: {process.pid})。")
                return process
            else:
                self.log_message("ERROR", f"❌ FFmpeg 启动后立即退出，返回码: {process.poll()}")
                return None
        except Exception as e:
            self.log_message("ERROR", f"❌ 执行 FFmpeg 时发生严重错误: {e}")
            return None

    def _log_ffmpeg_output(self, process):
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                if line: self.log_message("DEBUG", f"[FFmpeg] {line.strip()}")
            process.stdout.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        profile_path = sys.argv[1]
        if not os.path.isdir(profile_path):
            print(f"FATAL: Profile path '{profile_path}' not found.")
            sys.exit(1)
        streamer = Streamer(profile_path=profile_path)
        streamer.run()
    else:
        print("FATAL: No profile path provided. This script should be launched by manager.py")
