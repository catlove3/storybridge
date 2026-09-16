"""Edit the actual screen recording to 18 seconds; only add subtitles."""
import json,subprocess,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'/tmp/storybridge-video-tools')
import imageio_ffmpeg
ff=imageio_ffmpeg.get_ffmpeg_exe()
m=json.loads((ROOT/'recording_manifest.json').read_text())
durations=[4,4,6,4]
titles=['选一个改法：高考替考 → 赛艇履历造假','看依赖图：第三场的朋友也受影响','对照第三场：朋友的经历、她带来的证据一起改','读到结尾：名字和作品，终于都是她自己的']
small=['01  选择改编方案','02  追踪影响范围','03  查看真实改写','04  保留人物的选择']
for i,(seg,dur) in enumerate(zip(m['segments'],durations)):
 im=Image.new('RGBA',(1920,1080),(0,0,0,0));d=ImageDraw.Draw(im)
 d.rectangle((0,0,1920,103),fill=(21,45,60,247))
 d.rectangle((0,1003,1920,1080),fill=(21,45,60,247))
 d.text((52,21),titles[i],font=ImageFont.truetype('/mnt/c/Windows/Fonts/msyhbd.ttc',39),fill='white')
 d.text((52,1021),small[i],font=ImageFont.truetype('/mnt/c/Windows/Fonts/msyh.ttc',28),fill='#E4C589')
 d.text((1000,1023),'真实产品操作回放 · 已省略生成等待',font=ImageFont.truetype('/mnt/c/Windows/Fonts/msyh.ttc',26),fill='#CCDBDE')
 overlay=ROOT/'assets'/f'caption_{i}.png';im.save(overlay)
 ratio=dur/(seg['end']-seg['start'])
 filters=f"[0:v]trim=start={seg['start']}:end={seg['end']},setpts={ratio}*(PTS-STARTPTS),fps=30,tpad=stop_mode=clone:stop_duration=1,scale=1920:1080[v];[v][1:v]overlay=0:0,format=yuv420p[out]"
 cmd=[ff,'-hide_banner','-loglevel','error','-y','-i',m['raw_video'],'-i',str(overlay),'-filter_complex',filters,'-map','[out]','-t',str(dur),'-an','-c:v','libx264','-crf','18','-preset','fast',str(ROOT/'recordings'/f'clip_{i}.mp4')]
 subprocess.run(cmd,check=True)
lst=ROOT/'recordings/concat.txt';lst.write_text('\n'.join(f"file '{(ROOT/'recordings'/f'clip_{i}.mp4').resolve()}'" for i in range(4)))
out=ROOT.parent/'StoryBridge_18秒操作演示.mp4'
subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(lst),'-c','copy','-movflags','+faststart',str(out)],check=True)
subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-ss','8.8','-i',str(out),'-frames:v','1',str(ROOT/'assets/video_poster.png')],check=True)
check=subprocess.run([ff,'-hide_banner','-i',str(out),'-f','null','-'],capture_output=True,text=True)
(ROOT/'video_validation.txt').write_text(check.stderr);assert check.returncode==0
m['edited_video']=str(out);m['duration_seconds']=18;m['subtitles']=titles
(ROOT/'recording_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
print(out)
