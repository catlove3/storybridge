"""Cut the real UI recording into an 18-second silent MP4 with factual captions."""
import json,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent;CASE=ROOT/'rebirth_system_16k';ASSETS=CASE/'assets';REC=CASE/'recordings'
sys.path.insert(0,'/tmp/storybridge-video-tools')
import imageio_ffmpeg
ff=imageio_ffmpeg.get_ffmpeg_exe();m=json.loads((CASE/'recording_manifest.json').read_text())
durations=[4,4,5,5]
titles=['选择系统改法：统分后台 → EduSwap 黑箱模块','看依赖关系：哪些场景应当联动','核对结果：669 不变，330 与 487 对调','人工复核：法庭台词已经同步为 330']
subs=['01  选择系统方案','02  查看影响范围','03  审查分数反转','04  审查后续证据']
font='/mnt/c/Windows/Fonts/msyh.ttc';bold='/mnt/c/Windows/Fonts/msyhbd.ttc'
for i,(segment,duration) in enumerate(zip(m['segments'],durations)):
    overlay=Image.new('RGBA',(1280,720),(0,0,0,0));draw=ImageDraw.Draw(overlay)
    draw.rectangle((0,0,1280,70),fill=(21,45,60,248));draw.rectangle((0,668,1280,720),fill=(21,45,60,248))
    draw.text((34,15),titles[i],font=ImageFont.truetype(bold,26),fill='white')
    draw.text((34,681),subs[i],font=ImageFont.truetype(font,18),fill='#E4C589')
    draw.text((695,681),'真实产品回放 · 已省略模型等待',font=ImageFont.truetype(font,17),fill='#CCDADD')
    op=ASSETS/f'system_caption_{i}.png';overlay.save(op)
    source_duration=max(.2,segment['end']-segment['start']);ratio=duration/source_duration
    filters=f"[0:v]trim=start={segment['start']}:end={segment['end']},setpts={ratio}*(PTS-STARTPTS),fps=30,tpad=stop_mode=clone:stop_duration=1,scale=1280:720[v];[v][1:v]overlay=0:0,format=yuv420p[out]"
    subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-i',m['raw_video'],'-i',str(op),'-filter_complex',filters,'-map','[out]','-t',str(duration),'-an','-c:v','libx264','-crf','18','-preset','fast',str(REC/f'system_clip_{i}.mp4')],check=True)
concat=REC/'system_concat.txt';concat.write_text('\n'.join(f"file '{(REC/f'system_clip_{i}.mp4').resolve()}'" for i in range(4)))
out=ROOT.parent/'StoryBridge_18秒操作演示.mp4'
subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(out)],check=True)
subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-ss','8.5','-i',str(out),'-frames:v','1',str(ASSETS/'system_video_poster.png')],check=True)
probe=subprocess.run([ff,'-hide_banner','-i',str(out),'-f','null','-'],capture_output=True,text=True)
(CASE/'video_validation.txt').write_text(probe.stderr);assert probe.returncode==0
m.update({'edited_video':str(out),'duration_seconds':18,'captions':titles});(CASE/'recording_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
print(out)
