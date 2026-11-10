import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from backend.app.config import FFMPEG_PATH

class FFmpegService:
    def __init__(self, ffmpeg_bin: str = FFMPEG_PATH):
        self.ffmpeg_bin = ffmpeg_bin
        self._cached_installed: Optional[bool] = None
        self._cached_version: Optional[str] = None

    def check_installed(self) -> bool:
        if self._cached_installed is not None:
            return self._cached_installed
        if not self.ffmpeg_bin:
            self._cached_installed = False
            return False
        if os.path.isabs(self.ffmpeg_bin) and os.path.isfile(self.ffmpeg_bin):
            self._cached_installed = True
            return True
        self._cached_installed = shutil.which(self.ffmpeg_bin) is not None
        return self._cached_installed

    def _sync_get_version(self) -> str:
        if self._cached_version is not None:
            return self._cached_version
        if not self.check_installed():
            self._cached_version = "Chưa cài đặt"
            return self._cached_version
        try:
            res = subprocess.run([self.ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=5)
            self._cached_version = res.stdout.splitlines()[0] if res.stdout else "FFmpeg Ready"
            return self._cached_version
        except Exception as e:
            return f"Lỗi: {str(e)}"

    async def get_version(self) -> str:
        if self._cached_version is not None:
            return self._cached_version
        return await asyncio.to_thread(self._sync_get_version)

    def _sync_probe_video(self, video_path: str) -> Dict[str, Any]:
        if not os.path.exists(video_path):
            return {"error": "File không tồn tại", "duration": 0, "width": 0, "height": 0, "fps": 0, "has_audio": False}

        file_size = os.path.getsize(video_path)
        info = {
            "file_size": file_size,
            "duration": 0.0,
            "width": 0,
            "height": 0,
            "fps": 30.0,
            "video_codec": "unknown",
            "audio_codec": "none",
            "has_audio": False,
            "aspect_ratio": "9:16",
        }

        try:
            res = subprocess.run(
                [self.ffmpeg_bin, "-i", video_path],
                capture_output=True,
                text=True,
                timeout=15
            )
            output = res.stderr

            # Duration: 00:00:10.24, start: ...
            dur_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', output)
            if dur_match:
                h = int(dur_match.group(1))
                m = int(dur_match.group(2))
                s = float(dur_match.group(3))
                info["duration"] = round(h * 3600 + m * 60 + s, 2)

            # Video stream
            vid_match = re.search(r'Stream #\d+:\d+.*?: Video: ([^,\s]+).*?,\s*(\d+)x(\d+).*?,\s*([\d\.]+)\s*fps', output)
            if vid_match:
                info["video_codec"] = vid_match.group(1)
                info["width"] = int(vid_match.group(2))
                info["height"] = int(vid_match.group(3))
                info["fps"] = float(vid_match.group(4))
            else:
                res_match = re.search(r'(\d{3,4})x(\d{3,4})', output)
                if res_match:
                    info["width"] = int(res_match.group(1))
                    info["height"] = int(res_match.group(2))

            # Audio stream
            aud_match = re.search(r'Stream #\d+:\d+.*?: Audio: ([^,\s]+)', output)
            if aud_match:
                info["has_audio"] = True
                info["audio_codec"] = aud_match.group(1)

            if info["width"] > 0 and info["height"] > 0:
                ratio = round(info["width"] / info["height"], 2)
                if abs(ratio - (9 / 16)) < 0.05:
                    info["aspect_ratio"] = "9:16 (Dọc chuẩn TikTok)"
                elif abs(ratio - (16 / 9)) < 0.05:
                    info["aspect_ratio"] = "16:9 (Ngang)"
                elif abs(ratio - 1.0) < 0.05:
                    info["aspect_ratio"] = "1:1 (Vuông)"
                else:
                    info["aspect_ratio"] = f"{info['width']}:{info['height']}"

        except Exception as e:
            info["error"] = str(e)

        return info

    async def probe_video(self, video_path: str) -> Dict[str, Any]:
        return await asyncio.to_thread(self._sync_probe_video, video_path)

    def _sync_create_scene_motion_video(
        self,
        image_path: str,
        output_path: str,
        duration: float = 10.0,
        motion_type: str = "zoom_in",
        dialogue_text: Optional[str] = None,
        audio_path: Optional[str] = None,
        width: int = 1080,
        height: int = 1920,
        fps: int = 60
    ) -> Dict[str, Any]:
        """
        Creates a high-end 9:16 vertical commercial video from an image in ~1-2 seconds using FFmpeg.
        - zoom_in: Gentle commercial push-in zoom (Scene 1: model + product)
        - closeup: Dynamic macro push-in zoom (Scene 2: product details)
        - pan: Subtle commercial pan
        - fps: 60 fps for ultra-smooth TikTok motion
        - dialogue_text: Auto-generates natural Vietnamese TTS voiceover matching the script!
        """
        if not os.path.exists(image_path):
            return {"success": False, "error": f"Tệp ảnh không tồn tại: {image_path}"}

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        total_frames = int(duration * fps)

        # 1. Generate Vietnamese TTS audio if dialogue is provided
        temp_audio = audio_path
        if not temp_audio and dialogue_text and dialogue_text.strip():
            try:
                from gtts import gTTS
                clean_text = re.sub(r'["\']', '', dialogue_text).strip()
                if clean_text:
                    temp_audio_file = Path(output_path).parent / f"voice_{Path(output_path).stem}.mp3"
                    tts = gTTS(text=clean_text, lang='vi')
                    tts.save(str(temp_audio_file))
                    if temp_audio_file.exists() and temp_audio_file.stat().st_size > 500:
                        temp_audio = str(temp_audio_file)
            except Exception as e_tts:
                import logging
                logging.getLogger(__name__).warning(f"TTS voiceover error: {e_tts}")

        # 2. Build 60fps dynamic motion zoom filter
        if motion_type == "closeup":
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"zoompan=z='min(zoom+0.0005,1.22)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
            )
        elif motion_type == "pan":
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"zoompan=z=1.12:x='if(lte(on,1),(iw-iw/zoom)/2,x-0.2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
            )
        else:
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"zoompan=z='min(zoom+0.0003,1.14)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
            )

        cmd = [self.ffmpeg_bin, "-y", "-loop", "1", "-i", image_path]

        has_voice = False
        if temp_audio and os.path.exists(temp_audio):
            cmd.extend(["-i", temp_audio])
            has_voice = True

        cmd.extend([
            "-vf", vf,
            "-c:v", "libx264",
            "-r", str(fps),
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-crf", "19"
        ])

        if has_voice:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100",
                "-map", "0:v",
                "-map", "1:a"
            ])

        cmd.extend(["-movflags", "+faststart", output_path])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
                # Fallback to simple static pad if complex filter fails
                fallback_vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}"
                cmd_fallback = [
                    self.ffmpeg_bin, "-y",
                    "-loop", "1",
                    "-i", image_path
                ]
                if has_voice:
                    cmd_fallback.extend(["-i", temp_audio])

                cmd_fallback.extend([
                    "-vf", fallback_vf,
                    "-c:v", "libx264",
                    "-r", str(fps),
                    "-t", str(duration),
                    "-pix_fmt", "yuv420p",
                    "-preset", "ultrafast"
                ])
                if has_voice:
                    cmd_fallback.extend([
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-ar", "44100",
                        "-map", "0:v",
                        "-map", "1:a"
                    ])
                cmd_fallback.extend(["-movflags", "+faststart", output_path])

                res2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=60)
                if res2.returncode != 0:
                    return {"success": False, "error": f"Lỗi FFmpeg: {res2.stderr}"}

            probe = self._sync_probe_video(output_path)
            return {
                "success": True,
                "output_path": output_path,
                "file_name": os.path.basename(output_path),
                "duration": probe.get("duration", duration),
                "resolution": f"{width}x{height}",
                "fps": probe.get("fps", fps),
                "has_audio": probe.get("has_audio", False),
                "file_size": os.path.getsize(output_path)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_scene_motion_video(self, *args, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self._sync_create_scene_motion_video, *args, **kwargs)

    def _sync_stitch_videos(
        self,
        video1_path: str,
        video2_path: str,
        output_path: str,
        transition: str = "none",
        transition_duration: float = 0.5,
        target_width: int = 1080,
        target_height: int = 1920,
        target_fps: int = 60,
        volume: float = 1.0,
        trim_v1_start: float = 0.0,
        trim_v2_end: float = 0.0
    ) -> Dict[str, Any]:
        if not os.path.exists(video1_path):
            raise FileNotFoundError(f"Video 1 không tồn tại: {video1_path}")
        if not os.path.exists(video2_path):
            raise FileNotFoundError(f"Video 2 không tồn tại: {video2_path}")

        # Strict Anti-Duplicate Guard: NEVER stitch two identical videos into one
        import hashlib
        def _calc_quick_hash(p: str) -> str:
            h = hashlib.md5()
            with open(p, "rb") as fp:
                h.update(fp.read(65536))
            return h.hexdigest()

        if (os.path.abspath(video1_path) == os.path.abspath(video2_path) or
            (os.path.getsize(video1_path) == os.path.getsize(video2_path) and _calc_quick_hash(video1_path) == _calc_quick_hash(video2_path))):
            logger.warning(f"Prevented stitching identical scene videos: {video1_path} == {video2_path}")
            return {
                "success": False,
                "error": "Cảnh 1 và Cảnh 2 là 2 video giống hệt nhau (trùng lặp). Vui lòng tạo hoặc đổi Cảnh 2 trước khi ghép!"
            }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        v1_info = self._sync_probe_video(video1_path)
        v2_info = self._sync_probe_video(video2_path)

        scale_filter = (
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={target_fps},format=yuv420p,setpts=PTS-STARTPTS"
        )

        v1_audio = v1_info.get("has_audio", False)
        v2_audio = v2_info.get("has_audio", False)
        v1_dur = max(float(v1_info.get("duration") or 10.0), 1.0)
        v2_dur = max(float(v2_info.get("duration") or 10.0), 1.0)

        # Ultra-fast stream-copy path (~0.2s) when both videos are already standardized 1080x1920 @ 60fps H.264
        if (
            transition == "none"
            and volume == 1.0
            and trim_v1_start == 0
            and trim_v2_end == 0
            and v1_info.get("width") == target_width
            and v1_info.get("height") == target_height
            and v2_info.get("width") == target_width
            and v2_info.get("height") == target_height
            and abs(float(v1_info.get("fps") or 0) - target_fps) <= 1.5
            and abs(float(v2_info.get("fps") or 0) - target_fps) <= 1.5
            and v1_audio == v2_audio
        ):
            fast_list = Path(output_path).parent / f"fast_concat_{os.getpid()}.txt"
            try:
                with open(fast_list, "w", encoding="utf-8") as f:
                    f.write(f"file '{os.path.abspath(video1_path).replace(chr(92), '/')}'\n")
                    f.write(f"file '{os.path.abspath(video2_path).replace(chr(92), '/')}'\n")
                fast_cmd = [
                    self.ffmpeg_bin, "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", str(fast_list),
                    "-c", "copy",
                    "-movflags", "+faststart",
                    output_path
                ]
                fast_res = subprocess.run(fast_cmd, capture_output=True, text=True, timeout=30)
                if fast_res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                    fast_probe = self._sync_probe_video(output_path)
                    if float(fast_probe.get("duration") or 0) >= (v1_dur + v2_dur - 1.5):
                        return {
                            "success": True,
                            "output_path": output_path,
                            "file_name": os.path.basename(output_path),
                            "duration": fast_probe.get("duration", round(v1_dur + v2_dur, 2)),
                            "resolution": f"{target_width}x{target_height}",
                            "fps": fast_probe.get("fps", target_fps),
                            "file_size": os.path.getsize(output_path),
                            "has_audio": fast_probe.get("has_audio", v1_audio)
                        }
            except Exception:
                pass
            finally:
                if fast_list.exists():
                    try:
                        fast_list.unlink()
                    except Exception:
                        pass

        cmd = [self.ffmpeg_bin, "-y"]

        if trim_v1_start > 0:
            cmd.extend(["-ss", str(trim_v1_start)])
        cmd.extend(["-i", video1_path])
        cmd.extend(["-i", video2_path])

        filter_complex_parts = [
            f"[0:v]{scale_filter}[v0];",
            f"[1:v]{scale_filter}[v1];"
        ]

        if v1_audio and v2_audio:
            filter_complex_parts.append(
                f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a0];"
                f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a1];"
                f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v_out][a_out]"
            )
            has_out_audio = True
        elif v1_audio and not v2_audio:
            filter_complex_parts.append(
                f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a0];"
                f"anullsrc=channel_layout=stereo:sample_rate=44100:d={v2_dur}[a1_raw];"
                f"[a1_raw]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a1];"
                f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v_out][a_out]"
            )
            has_out_audio = True
        elif not v1_audio and v2_audio:
            filter_complex_parts.append(
                f"anullsrc=channel_layout=stereo:sample_rate=44100:d={v1_dur}[a0_raw];"
                f"[a0_raw]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a0];"
                f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,asetpts=PTS-STARTPTS[a1];"
                f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v_out][a_out]"
            )
            has_out_audio = True
        else:
            filter_complex_parts.append(
                f"[v0][v1]concat=n=2:v=1:a=0[v_out]"
            )
            has_out_audio = False

        filter_complex_str = "".join(filter_complex_parts)

        cmd.extend([
            "-filter_complex", filter_complex_str,
            "-map", "[v_out]"
        ])

        if has_out_audio:
            cmd.extend([
                "-map", "[a_out]",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100"
            ])
            if volume != 1.0:
                cmd.extend(["-filter:a", f"volume={volume}"])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", str(target_fps),
            "-movflags", "+faststart",
            output_path
        ])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if res.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
            # Fallback concat
            return self._sync_fallback_concat(video1_path, video2_path, output_path, target_width, target_height, target_fps)

        out_info = self._sync_probe_video(output_path)
        return {
            "success": True,
            "output_path": output_path,
            "file_name": os.path.basename(output_path),
            "duration": out_info.get("duration", round(v1_dur + v2_dur, 2)),
            "resolution": f"{out_info.get('width', target_width)}x{out_info.get('height', target_height)}",
            "fps": out_info.get("fps", target_fps),
            "file_size": out_info.get("file_size", os.path.getsize(output_path) if os.path.exists(output_path) else 0),
            "has_audio": out_info.get("has_audio", has_out_audio)
        }

    def _sync_fallback_concat(self, v1: str, v2: str, output: str, width: int, height: int, fps: int) -> Dict[str, Any]:
        # Standardize both inputs to uniform temp files if needed, then concat
        parent_dir = Path(output).parent
        list_file = parent_dir / "concat_list.txt"
        try:
            with open(list_file, "w", encoding="utf-8") as f:
                f.write(f"file '{os.path.abspath(v1).replace(chr(92), '/')}'\n")
                f.write(f"file '{os.path.abspath(v2).replace(chr(92), '/')}'\n")

            cmd = [
                self.ffmpeg_bin, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-movflags", "+faststart",
                output
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if os.path.exists(output) and os.path.getsize(output) > 1000:
                out_info = self._sync_probe_video(output)
                return {
                    "success": True,
                    "output_path": output,
                    "file_name": os.path.basename(output),
                    "duration": out_info.get("duration", 20.0),
                    "resolution": f"{width}x{height}",
                    "fps": fps,
                    "file_size": os.path.getsize(output),
                    "has_audio": out_info.get("has_audio", False)
                }
        finally:
            if list_file.exists():
                try:
                    list_file.unlink()
                except Exception:
                    pass
        return {"success": False, "error": "FFmpeg fallback concat failed"}

    async def stitch_videos(self, *args, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self._sync_stitch_videos, *args, **kwargs)

    def _sync_standardize_scene_video(
        self,
        input_video_path: str,
        output_video_path: str,
        dialogue_text: Optional[str] = None,
        target_width: int = 1080,
        target_height: int = 1920,
        target_fps: int = 60
    ) -> Dict[str, Any]:
        """
        Takes any video (e.g. downloaded from Google Flow) and standardizes it to:
        - Exactly 1080x1920 (9:16 vertical TikTok format)
        - Exactly 60.0 FPS
        - H.264 / AAC 44.1kHz audio
        - If the video has no audio and dialogue_text is provided, adds Vietnamese speech audio!
        """
        import uuid
        if not os.path.exists(input_video_path):
            return {"success": False, "error": f"Tệp video không tồn tại: {input_video_path}"}

        os.makedirs(os.path.dirname(output_video_path), exist_ok=True)
        probe = self._sync_probe_video(input_video_path)
        has_orig_audio = probe.get("has_audio", False)

        temp_audio = None
        if dialogue_text and not has_orig_audio:
            try:
                from gtts import gTTS
                temp_audio = str(Path(output_video_path).parent / f"temp_speech_{uuid.uuid4().hex[:6]}.mp3")
                tts = gTTS(text=dialogue_text.strip(), lang='vi', tld='com.vn', slow=False)
                tts.save(temp_audio)
            except Exception as e:
                logger.warning(f"gTTS audio generation error: {e}")
                temp_audio = None

        vf = (
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={target_fps}"
        )

        cmd = [self.ffmpeg_bin, "-y", "-i", input_video_path]
        if temp_audio and os.path.exists(temp_audio):
            cmd.extend(["-i", temp_audio])

        cmd.extend([
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-r", str(target_fps)
        ])

        if temp_audio and os.path.exists(temp_audio):
            cmd.extend([
                "-map", "0:v",
                "-map", "1:a",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100"
            ])
        elif has_orig_audio:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "44100"
            ])
        else:
            # Generate silent audio track so concat works seamlessly
            cmd.extend([
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-map", "0:v",
                "-map", "1:a",
                "-c:a", "aac",
                "-shortest"
            ])

        cmd.extend(["-movflags", "+faststart", output_video_path])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if temp_audio and os.path.exists(temp_audio):
                try:
                    os.unlink(temp_audio)
                except Exception:
                    pass

            if res.returncode != 0 or not os.path.exists(output_video_path) or os.path.getsize(output_video_path) < 1000:
                return {"success": False, "error": f"Lỗi FFmpeg: {res.stderr}"}

            out_probe = self._sync_probe_video(output_video_path)
            return {
                "success": True,
                "output_path": output_video_path,
                "file_name": os.path.basename(output_video_path),
                "duration": out_probe.get("duration", 10.0),
                "resolution": f"{target_width}x{target_height}",
                "fps": out_probe.get("fps", target_fps),
                "has_audio": out_probe.get("has_audio", False),
                "file_size": os.path.getsize(output_video_path)
            }
        except Exception as e:
            if temp_audio and os.path.exists(temp_audio):
                try:
                    os.unlink(temp_audio)
                except Exception:
                    pass
            return {"success": False, "error": str(e)}

    async def standardize_scene_video(self, *args, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self._sync_standardize_scene_video, *args, **kwargs)

    async def stitch_scenes(
        self,
        project_id: str,
        video1_path: str,
        video2_path: str,
        product_slug: str = "tiktok",
        transition: str = "none",
        volume: float = 1.0
    ) -> Dict[str, Any]:
        from backend.app.config import PROJECTS_DIR
        out_dir = PROJECTS_DIR / project_id / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{product_slug}_final.mp4"
        output_path = str(out_dir / file_name)

        res = await self.stitch_videos(
            video1_path=video1_path,
            video2_path=video2_path,
            output_path=output_path,
            transition=transition,
            volume=volume
        )
        if res.get("success"):
            res["final_video_path"] = output_path
            res["file_name"] = file_name
            res["url"] = f"/data/projects/{project_id}/exports/{file_name}"
        return res

ffmpeg_service = FFmpegService()
