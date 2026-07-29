#!/usr/bin/env python3
"""render.py - meta.json → output.html 뷰어 생성

사용법:
    python _tools/render.py                     # meta.json → output.html
    python _tools/render.py path/to/meta.json   # 지정 경로
"""
import json, sys, os, re
import html as _html

def esc(s):
    return _html.escape(str(s))

def js(s):
    return json.dumps(s, ensure_ascii=False)

def js_attr(s):
    """JS string literal safe for embedding inside an HTML attribute (double-quote delimited)."""
    return _html.escape(json.dumps(s, ensure_ascii=False), quote=True)

# ────────────────────────────────────────────
# 문장 분리
# ────────────────────────────────────────────
_SENT_RE = re.compile(
    r'(?<=[다요죠니까세뇨])\.\s*'
    r'|(?<=[다요죠니까세뇨])(?=\s*\n)'
    r'|(?<=습니다)\.\s*'
    r'|(?<=겁니다)\.\s*'
    r'|(?<=됩니다)\.\s*'
    r'|(?<=입니다)\.\s*'
    r'|(?<=합니다)\.\s*'
    r'|(?<=봅니다)\.\s*'
    r'|(?<=옵니다)\.\s*'
)

def split_sentences(text):
    sents = []
    for para in text.split('\n\n'):
        para = para.strip()
        if not para:
            continue
        parts = _SENT_RE.split(para)
        for p in parts:
            p = p.strip()
            if p:
                sents.append(p)
        sents.append('')  # paragraph break marker
    while sents and sents[-1] == '':
        sents.pop()
    return sents

def build_reading_html(text):
    if not text:
        return '<p style="color:#888">대본 데이터 없음</p>'
    sents = split_sentences(text)
    parts = []
    for s in sents:
        if s == '':
            parts.append('<br><br>')
        else:
            parts.append(f'<span class="sent">{esc(s)}</span> ')
    return ''.join(parts)

def build_news_html(text):
    if not text:
        return '<p style="color:#888">뉴스·공시 데이터 없음</p>'
    lines = text.strip().split('\n')
    cards = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        is_star = line.startswith('★') or line.startswith('- ★')
        line_clean = line.lstrip('-').lstrip('★').strip()
        cls = 'nd-star' if is_star else 'nd-item'
        cards.append(f'<div class="{cls}">{esc(line_clean)}</div>')
    return '\n'.join(cards)

def build_titles_html(titles):
    if not titles:
        return '<p style="color:#888">제목 데이터 없음</p>'
    parts = []
    for i, t in enumerate(titles):
        t = t.strip()
        if not t:
            continue
        # 번호 접두사 제거
        t_clean = re.sub(r'^\d+[\.\)]\s*', '', t)
        parts.append(
            f'<div class="yt-title-row">'
            f'<span class="yt-num">{i+1}</span>'
            f'<span class="yt-title-text">{esc(t_clean)}</span>'
            f'<button class="copy-sm" onclick="cpText(this,{js_attr(t_clean)})">복사</button>'
            f'</div>'
        )
    return '\n'.join(parts)

# ────────────────────────────────────────────
# CSS
# ────────────────────────────────────────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;background:#f4efe6;color:#2c2218;display:flex;height:100vh;overflow:hidden}
.sidebar{width:220px;min-width:220px;background:#faf6ee;border-right:1px solid #e0d8cb;display:flex;flex-direction:column;padding:16px 12px;gap:6px;overflow-y:auto}
.stock-hdr{text-align:center;padding:12px 0 8px;border-bottom:1px solid #e0d8cb;margin-bottom:8px}
.stock-name{font-size:22px;font-weight:800;color:#2c2218}
.kw-badge{display:inline-block;margin-top:6px;padding:3px 12px;border-radius:20px;background:#b5613f;color:#fff;font-size:12px;font-weight:700}
.nav-btn{display:flex;align-items:center;gap:8px;padding:10px 12px;border:none;background:transparent;border-radius:8px;cursor:pointer;font-size:14px;color:#5a4e3f;text-align:left;width:100%;transition:.15s}
.nav-btn:hover{background:#efe8db}
.nav-btn.active{background:#b5613f;color:#fff;font-weight:700}
.nav-icon{font-size:17px;width:24px;text-align:center}
.main{flex:1;overflow:hidden;display:flex;flex-direction:column}
.panel{flex:1;display:flex;flex-direction:column;overflow:hidden}
.card{flex:1;display:flex;flex-direction:column;margin:12px;border-radius:12px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08);overflow:hidden}
.bar{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid #efe8db;background:#faf6ee}
.bar .title{font-weight:700;font-size:15px;color:#2c2218}
.copy{padding:5px 14px;border:1px solid #d4c9b8;border-radius:6px;background:#fff;color:#5a4e3f;cursor:pointer;font-size:13px;font-weight:600;transition:.15s}
.copy:hover{background:#b5613f;color:#fff;border-color:#b5613f}
.copy.done{background:#4a8c5c;color:#fff;border-color:#4a8c5c}
.body{padding:16px;overflow-y:auto;flex:1;min-height:0;line-height:1.8;font-size:15px;color:#3d3225}
.rbody{padding:20px 24px;overflow-y:auto;flex:1;min-height:0;line-height:2;font-size:25px;color:#2c2218}
.sent{transition:background .15s}
.sync-active{background:#ffeeba;border-radius:3px}
.sync-done{color:#a89880}

/* 싱크 컨트롤 */
.sync-bar{padding:10px 16px;border-top:1px solid #efe8db;background:#faf6ee;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.sync-bar button{padding:6px 14px;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700}
.sync-bar .play-btn{background:#b5613f;color:#fff}
.sync-bar .play-btn.playing{background:#c97a5a}
.sync-bar .stop-btn{background:#d4c9b8;color:#3d3225}
.progress-wrap{flex:1;min-width:120px;height:8px;background:#e0d8cb;border-radius:4px;position:relative;cursor:pointer}
.progress-fill{height:100%;background:#b5613f;border-radius:4px;width:0;transition:width .1s linear}
.progress-knob{width:14px;height:14px;border-radius:50%;background:#b5613f;border:2px solid #fff;position:absolute;top:-3px;left:0;transform:translateX(-50%);box-shadow:0 1px 3px rgba(0,0,0,.2)}
.time-label{font-size:12px;color:#8a7d6d;white-space:nowrap}
.fz-wrap{display:flex;gap:4px}
.fz-btn{width:30px;height:30px;border:1px solid #d4c9b8;border-radius:6px;background:#fff;cursor:pointer;font-size:16px;color:#5a4e3f}

/* TTS 패널 */
.tts-body{padding:16px;overflow-y:auto;flex:1;min-height:0;white-space:pre-wrap;line-height:1.9;font-size:15px;color:#3d3225;font-family:'Apple SD Gothic Neo','Malgun Gothic',monospace}

/* 뉴스 패널 */
.nd-star{padding:10px 14px;margin:6px 0;border-radius:8px;background:#fff7ed;border-left:4px solid #b5613f;font-weight:600;line-height:1.6}
.nd-item{padding:8px 14px;margin:4px 0;border-radius:8px;background:#faf6ee;border-left:3px solid #d4c9b8;line-height:1.6}

/* 유튜브 패널 */
.yt-section{margin:8px 0;border:1px solid #efe8db;border-radius:10px;overflow:hidden}
.yt-hdr{display:flex;align-items:center;gap:8px;padding:12px 16px;background:#faf6ee;cursor:pointer;font-weight:700;font-size:14px;border:none;width:100%;text-align:left;color:#2c2218}
.yt-hdr:hover{background:#efe8db}
.yt-hdr::before{content:'▶';font-size:11px;transition:transform .2s}
.yt-section.open .yt-hdr::before{transform:rotate(90deg)}
.yt-content{display:none;padding:12px 16px;border-top:1px solid #efe8db}
.yt-section.open .yt-content{display:block}
.yt-title-row{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #f5f0e8}
.yt-title-row:last-child{border-bottom:none}
.yt-num{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#b5613f;color:#fff;font-size:12px;font-weight:700;flex-shrink:0}
.yt-title-text{flex:1;font-size:14px;line-height:1.5}
.copy-sm{padding:3px 10px;border:1px solid #d4c9b8;border-radius:5px;background:#fff;color:#5a4e3f;cursor:pointer;font-size:12px;flex-shrink:0;transition:.15s}
.copy-sm:hover{background:#b5613f;color:#fff;border-color:#b5613f}
.copy-sm.done{background:#4a8c5c;color:#fff;border-color:#4a8c5c}
.yt-pre{white-space:pre-wrap;font-size:14px;line-height:1.7;color:#3d3225;background:#faf6ee;padding:12px;border-radius:8px}
.yt-copy-row{display:flex;justify-content:flex-end;margin-top:8px}

/* 음성 병합 패널 (다크) */
.dark-panel{background:#0c1219;color:#e6e9ef}
.dark-panel .card{background:#1a2332;box-shadow:0 1px 4px rgba(0,0,0,.3)}
.dark-panel .bar{background:#1e2b3d;border-color:#2c3a52}
.dark-panel .bar .title{color:#e6e9ef}
.drop-zone{border:2px dashed #2c3a52;border-radius:10px;padding:18px;text-align:center;cursor:pointer;transition:.15s;margin:6px 0}
.drop-zone:hover,.drop-zone.over{border-color:#b5613f;background:rgba(181,97,63,.08)}
.drop-zone.loaded{border-color:#4a8c5c;background:rgba(74,140,92,.06)}
.drop-text{color:#8a9ab5;font-size:14px;margin-top:4px}
.merge-ctrl{display:flex;align-items:center;gap:12px;margin:10px 0;flex-wrap:wrap}
.merge-btn{padding:10px 22px;border:none;border-radius:8px;background:#b5613f;color:#fff;font-weight:700;cursor:pointer;font-size:14px}
.merge-btn:disabled{opacity:.4;cursor:default}
.merge-result{margin-top:10px;padding:12px;border-radius:8px;background:#162030}
.dl-btn{padding:8px 18px;border:none;border-radius:7px;background:#2e7d5b;color:#fff;font-weight:700;cursor:pointer;font-size:14px;margin-right:8px}
.go-sync-btn{padding:8px 18px;border:none;border-radius:7px;background:#3a4a63;color:#fff;font-weight:700;cursor:pointer;font-size:14px}
.merge-status{color:#8a9ab5;font-size:13px;margin-top:6px;min-height:18px}

/* TTS 검증 패널 (다크) */
.tc-desc{color:#9aa4b2;font-size:14px;line-height:1.6;margin-bottom:12px}
.tc-desc b{color:#cdd3dc}
.tc-key-row{display:flex;gap:8px;margin-bottom:10px}
.tc-key-input{flex:1;padding:9px 11px;border-radius:7px;border:1px solid #2c3a52;background:#0e1622;color:#e6e9ef;font-size:13px}
.tc-key-btn{padding:9px 18px;border-radius:7px;border:0;background:#3a4a63;color:#fff;font-weight:700;cursor:pointer;font-size:14px}
.tc-drop{border:2px dashed #2c3a52;border-radius:9px;padding:20px;text-align:center;cursor:pointer;transition:.15s}
.tc-run-btn{padding:9px 22px;border-radius:7px;border:0;background:#2e7d5b;color:#fff;font-weight:700;cursor:pointer;font-size:14px}

@media(max-width:700px){
  body{flex-direction:column}
  .sidebar{width:100%;min-width:0;flex-direction:row;overflow-x:auto;padding:8px;gap:4px;height:auto;min-height:auto;border-right:none;border-bottom:1px solid #e0d8cb}
  .stock-hdr{display:none}
  .nav-btn{padding:8px 12px;white-space:nowrap;font-size:13px}
  .rbody{font-size:20px;padding:14px}
}
"""

# ────────────────────────────────────────────
# JavaScript (core)
# ────────────────────────────────────────────
JS_CORE = r"""
var cats=["reading","tts","chat0","youtube","audiomerge","ttscheck"];
var curIdx=0;

function showCat(id){
  cats.forEach(function(c,i){
    document.getElementById('panel-'+c).style.display=c===id?'':'none';
    if(c===id)curIdx=i;
  });
  document.querySelectorAll('.nav-btn').forEach(function(b){
    b.classList.toggle('active',b.getAttribute('data-cat')===id);
  });
}

function cpRaw(id){
  var text=RAW[id]||'';
  navigator.clipboard.writeText(text).then(function(){
    var panel=document.getElementById('panel-'+id);
    var btn=panel.querySelector('.copy');
    if(!btn)return;
    btn.classList.add('done');
    var orig=btn.textContent;
    btn.textContent='✅ 복사됨';
    setTimeout(function(){btn.classList.remove('done');btn.textContent=orig;},1200);
  });
}

function cpText(btn,text){
  navigator.clipboard.writeText(text).then(function(){
    btn.classList.add('done');
    var orig=btn.textContent;
    btn.textContent='✅ 복사됨';
    setTimeout(function(){btn.classList.remove('done');btn.textContent=orig;},1200);
  });
}

function toggleYt(el){
  var sec=el.closest('.yt-section');
  sec.classList.toggle('open');
}

var rsz=25;
function fz(d){
  rsz=Math.max(14,Math.min(48,rsz+d));
  var el=document.getElementById('reading');
  if(el)el.style.fontSize=rsz+'px';
}

document.addEventListener('keydown',function(e){
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){
    e.preventDefault();
    curIdx=e.key==='ArrowDown'?Math.min(curIdx+1,cats.length-1):Math.max(curIdx-1,0);
    showCat(cats[curIdx]);
  }
  if((e.key==='c'||e.key==='C')&&!e.ctrlKey&&!e.metaKey){cpRaw(cats[curIdx]);}
  if(e.key===' '&&syncAudio&&!e.ctrlKey&&!e.metaKey){
    var tag=document.activeElement.tagName;
    if(tag==='INPUT'||tag==='TEXTAREA'||tag==='BUTTON')return;
    if(cats[curIdx]==='reading'){e.preventDefault();toggleSync();}
  }
});
"""

# ────────────────────────────────────────────
# JavaScript (audio merge)
# ────────────────────────────────────────────
JS_AUDIO = r"""
var actx=null,buffers=[null,null],mergedBlob=null;
function getCtx(){if(!actx)actx=new(window.AudioContext||window.webkitAudioContext)();return actx;}
function fmtTime(s){var m=Math.floor(s/60),ss=(s%60).toFixed(1);return m+':'+(ss<10?'0':'')+ss;}

function loadAudio(n,input){
  var file=input.files[0];if(!file)return;
  var drop=document.getElementById('drop'+n),aud=document.getElementById('audio'+n),dur=document.getElementById('dur'+n),status=document.getElementById('merge-status');
  status.textContent='TTS '+n+' 로딩 중...';
  aud.src=URL.createObjectURL(file);aud.style.display='block';
  drop.querySelector('.drop-text').textContent=file.name;drop.classList.add('loaded');
  var reader=new FileReader();
  reader.onload=function(e){getCtx().decodeAudioData(e.target.result,function(buf){
    buffers[n-1]=buf;dur.textContent=fmtTime(buf.duration);
    status.textContent='TTS '+n+' 로드 완료 ('+fmtTime(buf.duration)+')';
    document.getElementById('mergeBtn').disabled=!(buffers[0]&&buffers[1]);
  },function(){status.textContent='⚠️ TTS '+n+' 디코딩 실패';});};
  reader.readAsArrayBuffer(file);
}

['drop1','drop2'].forEach(function(id,i){
  var el=document.getElementById(id);if(!el)return;
  el.addEventListener('dragover',function(e){e.preventDefault();el.classList.add('over');});
  el.addEventListener('dragleave',function(){el.classList.remove('over');});
  el.addEventListener('drop',function(e){
    e.preventDefault();el.classList.remove('over');
    var f=e.dataTransfer.files[0];if(f){var inp=document.getElementById('file'+(i+1));var dt=new DataTransfer();dt.items.add(f);inp.files=dt.files;loadAudio(i+1,inp);}
  });
});

function resetAll(){
  buffers=[null,null];mergedBlob=null;
  [1,2].forEach(function(n){
    var drop=document.getElementById('drop'+n),aud=document.getElementById('audio'+n),dur=document.getElementById('dur'+n),inp=document.getElementById('file'+n);
    drop.classList.remove('loaded');drop.querySelector('.drop-text').textContent='TTS '+n+' 파일을 여기에 드래그하거나 클릭';
    aud.style.display='none';aud.src='';dur.textContent='';inp.value='';
  });
  document.getElementById('mergeBtn').disabled=true;
  document.getElementById('merge-result').style.display='none';
  document.getElementById('audio-out').src='';document.getElementById('dur-out').textContent='';
  document.getElementById('merge-status').textContent='초기화 완료';
}

var xfSlider=document.getElementById('xfade'),xfVal=document.getElementById('xfade-val');
if(xfSlider)xfSlider.addEventListener('input',function(){xfVal.textContent=(this.value/1000).toFixed(1)+'초';});

function mergeAudio(){
  var b1=buffers[0],b2=buffers[1];if(!b1||!b2)return;
  var status=document.getElementById('merge-status');status.textContent='병합 중...';
  var sr=b1.sampleRate,ctx=getCtx(),ch=Math.max(b1.numberOfChannels,b2.numberOfChannels);
  var xfade=parseFloat(document.getElementById('xfade').value)/1000;
  var xfSamples=Math.min(Math.floor(xfade*sr),b1.length,b2.length);
  var outLen=b1.length+b2.length-xfSamples,out=ctx.createBuffer(ch,outLen,sr);
  for(var c=0;c<ch;c++){
    var od=out.getChannelData(c),d1=b1.getChannelData(Math.min(c,b1.numberOfChannels-1)),d2=b2.getChannelData(Math.min(c,b2.numberOfChannels-1));
    for(var i=0;i<b1.length-xfSamples;i++)od[i]=d1[i];
    var fadeStart=b1.length-xfSamples;
    for(var i=0;i<xfSamples;i++){var t=i/xfSamples;od[fadeStart+i]=d1[fadeStart+i]*(1-t)+d2[i]*t;}
    var b2Start=b1.length;
    for(var i=xfSamples;i<d2.length;i++)od[b2Start-xfSamples+i]=d2[i];
  }
  mergedBlob=encodeWAV(out);
  var url=URL.createObjectURL(mergedBlob);
  document.getElementById('audio-out').src=url;
  document.getElementById('dur-out').textContent=fmtTime(out.duration);
  document.getElementById('merge-result').style.display='';
  status.textContent='✅ 병합 완료 — '+fmtTime(out.duration);
  setTimeout(useMergedForSync,300);
}

function encodeWAV(buffer){
  var ch=buffer.numberOfChannels,sr=buffer.sampleRate,len=buffer.length,bps=16;
  var byteRate=sr*ch*bps/8,blockAlign=ch*bps/8,dataSize=len*ch*2;
  var buf=new ArrayBuffer(44+dataSize),v=new DataView(buf);
  function s(o,str){for(var i=0;i<str.length;i++)v.setUint8(o+i,str.charCodeAt(i));}
  s(0,'RIFF');v.setUint32(4,36+dataSize,true);s(8,'WAVE');s(12,'fmt ');
  v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,ch,true);
  v.setUint32(24,sr,true);v.setUint32(28,byteRate,true);v.setUint16(32,blockAlign,true);
  v.setUint16(34,bps,true);s(36,'data');v.setUint32(40,dataSize,true);
  var off=44,channels=[];for(var c=0;c<ch;c++)channels.push(buffer.getChannelData(c));
  for(var i=0;i<len;i++){for(var c=0;c<ch;c++){var s16=Math.max(-1,Math.min(1,channels[c][i]));v.setInt16(off,s16<0?s16*0x8000:s16*0x7FFF,true);off+=2;}}
  return new Blob([buf],{type:'audio/wav'});
}

function downloadMerged(){
  if(!mergedBlob)return;var a=document.createElement('a');
  a.href=URL.createObjectURL(mergedBlob);a.download=stockName+'_'+fileDate+'_TTS.wav';a.click();
}

function goSync(){if(!mergedBlob)return;useMergedForSync();showCat('reading');}

function syncSingle(){
  var inp=document.getElementById('file1');
  if(!inp||!inp.files||!inp.files[0])inp=document.getElementById('file2');
  if(!inp||!inp.files||!inp.files[0]){document.getElementById('merge-status').textContent='⚠️ 먼저 음성 파일을 올려주세요';return;}
  loadSyncAudio(inp);showCat('reading');
}
"""

# ────────────────────────────────────────────
# JavaScript (sync playback)
# ────────────────────────────────────────────
JS_SYNC = r"""
var syncAudio=null,syncTimings=[],syncRAF=null,syncPlaying=false;

function loadSyncAudio(input){
  var file=input.files?input.files[0]:input;if(!file)return;
  var nameEl=document.getElementById('sync-name');nameEl.textContent=file.name+' 로딩 중...';
  var reader=new FileReader();
  reader.onload=function(e){getCtx().decodeAudioData(e.target.result,function(buf){
    if(!syncAudio)syncAudio=new Audio();
    syncAudio.src=URL.createObjectURL(file);syncAudio._duration=buf.duration;
    nameEl.textContent=file.name+' ('+fmtTime(buf.duration)+')';
    document.getElementById('syncPlayBtn').disabled=false;
    buildSyncTimings(buf.duration);updateSyncBar(0,buf.duration);
  },function(){nameEl.textContent='⚠️ 디코딩 실패';});};
  reader.readAsArrayBuffer(file);
}

function useMergedForSync(){
  if(!mergedBlob)return;
  var nameEl=document.getElementById('sync-name');nameEl.textContent='병합 음성 로딩 중...';
  var reader=new FileReader();
  reader.onload=function(e){getCtx().decodeAudioData(e.target.result,function(buf){
    if(!syncAudio)syncAudio=new Audio();
    syncAudio.src=URL.createObjectURL(mergedBlob);syncAudio._duration=buf.duration;
    nameEl.textContent='병합 음성 ('+fmtTime(buf.duration)+')';
    document.getElementById('syncPlayBtn').disabled=false;
    buildSyncTimings(buf.duration);updateSyncBar(0,buf.duration);
  });};
  reader.readAsArrayBuffer(mergedBlob);
}

function buildSyncTimings(totalDur){
  syncTimings=[];var reading=document.getElementById('reading');if(!reading)return;
  var ps=reading.querySelectorAll('.sent'),totalChars=0,charCounts=[];
  ps.forEach(function(p){var c=p.textContent.replace(/\s+/g,'').length;charCounts.push(c);totalChars+=c;});
  if(totalChars===0)return;var t=0;
  ps.forEach(function(p,i){var dur=(charCounts[i]/totalChars)*totalDur;syncTimings.push({el:p,start:t,end:t+dur});t+=dur;});
}

function toggleSync(){
  if(!syncAudio)return;
  if(syncPlaying){syncAudio.pause();syncPlaying=false;cancelAnimationFrame(syncRAF);
    var btn=document.getElementById('syncPlayBtn');btn.textContent='▶ 싱크 재생';btn.classList.remove('playing');return;}
  if(syncAudio.ended||syncAudio.currentTime===0)clearSyncClasses();
  syncAudio.play();syncPlaying=true;
  var btn=document.getElementById('syncPlayBtn');btn.textContent='⏸ 일시정지';btn.classList.add('playing');
  syncTick();
  syncAudio.onended=function(){syncPlaying=false;cancelAnimationFrame(syncRAF);
    var btn=document.getElementById('syncPlayBtn');btn.textContent='▶ 싱크 재생';btn.classList.remove('playing');
    updateSyncBar(syncDur(),syncDur());};
}

function stopSync(){
  if(!syncAudio)return;syncAudio.pause();syncAudio.currentTime=0;syncPlaying=false;cancelAnimationFrame(syncRAF);clearSyncClasses();
  var btn=document.getElementById('syncPlayBtn');btn.textContent='▶ 싱크 재생';btn.classList.remove('playing');updateSyncBar(0,syncDur());
}

function clearSyncClasses(){var r=document.getElementById('reading');if(!r)return;r.querySelectorAll('.sent').forEach(function(p){p.classList.remove('sync-active','sync-done');});}
function syncDur(){return(syncAudio&&(syncAudio._duration||syncAudio.duration))||1;}

function updateSyncBar(ct,dur){
  var pct=Math.max(0,Math.min(100,(ct/dur)*100));
  document.getElementById('sync-fill').style.width=pct.toFixed(2)+'%';
  document.getElementById('sync-knob').style.left=pct.toFixed(2)+'%';
  var cur=document.getElementById('sync-cur');if(cur)cur.textContent=fmtTime(ct);
  var de=document.getElementById('sync-dur');if(de)de.textContent=fmtTime(dur);
}

function updateSyncHighlight(ct,dur,doScroll){
  var activeIdx=-1;
  for(var i=0;i<syncTimings.length;i++){var s=syncTimings[i];if(ct>=s.start&&ct<s.end){activeIdx=i;break;}}
  if(activeIdx===-1&&ct>=dur*0.99)activeIdx=syncTimings.length-1;
  syncTimings.forEach(function(s,i){
    if(i<activeIdx){s.el.classList.remove('sync-active');s.el.classList.add('sync-done');}
    else if(i===activeIdx){s.el.classList.add('sync-active');s.el.classList.remove('sync-done');if(doScroll)s.el.scrollIntoView({behavior:'smooth',block:'center'});}
    else{s.el.classList.remove('sync-active','sync-done');}
  });
}

function syncTick(){if(!syncPlaying||!syncAudio)return;var ct=syncAudio.currentTime,dur=syncDur();updateSyncBar(ct,dur);updateSyncHighlight(ct,dur,true);syncRAF=requestAnimationFrame(syncTick);}

var seekDragging=false;
function seekToClientX(clientX){if(!syncAudio)return;var bar=document.getElementById('sync-progress');var rect=bar.getBoundingClientRect();var ratio=(clientX-rect.left)/rect.width;ratio=Math.max(0,Math.min(1,ratio));var dur=syncDur();var ct=ratio*dur;syncAudio.currentTime=ct;updateSyncBar(ct,dur);updateSyncHighlight(ct,dur,false);}
function seekStart(e){if(!syncAudio)return;e.preventDefault();seekDragging=true;seekToClientX(e.clientX);document.addEventListener('pointermove',seekMove);document.addEventListener('pointerup',seekEnd);}
function seekMove(e){if(!seekDragging)return;seekToClientX(e.clientX);}
function seekEnd(e){if(!seekDragging)return;seekDragging=false;document.removeEventListener('pointermove',seekMove);document.removeEventListener('pointerup',seekEnd);if(syncPlaying){var p=syncAudio.play();if(p&&p.catch)p.catch(function(){});}}
"""

# ────────────────────────────────────────────
# JavaScript (TTS check - Groq Whisper)
# ────────────────────────────────────────────
JS_TTSCHECK = r"""
(function(){
var DIG="영일이삼사오육칠팔구";
var N1=["","한","두","세","네","다섯","여섯","일곱","여덟","아홉"];
var N10=["","열","스물","서른","마흔","쉰","예순","일흔","여든","아흔"];
var NUMSYL="영공일이삼사오육칠팔구십백천만억조점";
function conv4(c){var s="",th=Math.floor(c/1000),h=Math.floor(c%1000/100),t=Math.floor(c%100/10),o=c%10;if(th)s+=(th==1?"":DIG[th])+"천";if(h)s+=(h==1?"":DIG[h])+"백";if(t)s+=(t==1?"":DIG[t])+"십";if(o)s+=DIG[o];return s;}
function sino(n){n=Math.floor(+n);if(n===0)return "영";var jo=Math.floor(n/1e12),eok=Math.floor(n/1e8)%10000,man=Math.floor(n/1e4)%10000,ones=n%10000,p="";if(jo)p+=conv4(jo)+"조";if(eok)p+=conv4(eok)+"억";if(man)p+=(man==1?"":conv4(man))+"만";if(ones)p+=conv4(ones);return p;}
function nat(n){n=Math.floor(+n);if(n<=0||n>=100)return sino(n);return N10[Math.floor(n/10)]+N1[n%10];}
function numko(text){var MV={"만":10000,"천":1000,"백":100,"십":10};text=text.replace(/\d+\s*만\s*\d+\s*천(?:\s*\d+\s*백)?(?:\s*\d+\s*십)?|\d+\s*천\s*\d+\s*백(?:\s*\d+\s*십)?|\d+\s*백\s*\d+\s*십/g,function(m){var val=0,prev=1e12,re=/(\d+)\s*([만천백십])/g,mm,ok=true;while((mm=re.exec(m))){var v=MV[mm[2]];if(v>=prev){ok=false;break;}val+=(+mm[1])*v;prev=v;}return(ok&&val)?sino(val):m;});text=text.replace(/(\d+)\s*([천백십])(?!\s*\d*\s*[조억만천백십])/g,function(m,a,u){return sino((+a)*MV[u]);});text=text.replace(/([\d,]+)(조|억|만)/g,function(m,a,g){var c=parseInt(a.replace(/,/g,''),10);if(isNaN(c))return m;if(g=="만"&&c==1)return "만";return sino(c)+g;});text=text.replace(/(\d+)\.(\d+)\s*(퍼센트|퍼|%|배|원|달러|개월|년)?/g,function(m,i,d,u){u=u||"";if(u=="%")u="퍼센트";var ds="",k;for(k=0;k<d.length;k++)ds+=DIG[+d[k]];return sino(i)+"점"+ds+u;});text=text.replace(/([\d,]+)\s*배/g,function(m,a){var c=parseInt(a.replace(/,/g,''),10);if(isNaN(c))return m;return(c<=30?nat(c):sino(c))+"배";});text=text.replace(/([\d,]+)\s*%/g,function(m,a){return sino(parseInt(a.replace(/,/g,''),10))+"퍼센트";});text=text.replace(/[\d,]*\d/g,function(m){var c=parseInt(m.replace(/,/g,''),10);return isNaN(c)?m:sino(c);});return text;}
function isHan(ch){return ch>="가"&&ch<="힣";}
function normRef(text){var s="",pos=[],i;for(i=0;i<text.length;i++){if(isHan(text[i])){s+=text[i];pos.push(i);}}return{s:s,pos:pos};}
function tcDoe(t){["현재가","목표가","신고가","평단가","추천가","종가","저가","고가"].forEach(function(w){t=t.split(w).join(w.slice(0,-1)+"까");});return t;}
function normHyp(segs){var s="",tm=[],i,j;for(i=0;i<segs.length;i++){var t=+segs[i].start||0,txt=tcDoe(numko(segs[i].text||''));for(j=0;j<txt.length;j++){if(isHan(txt[j])){s+=txt[j];tm.push(t);}}}return{s:s,tm:tm};}
function blocks(a,b){var b2j={},i;for(i=0;i<b.length;i++){(b2j[b[i]]=b2j[b[i]]||[]).push(i);}function fl(alo,ahi,blo,bhi){var bi=alo,bj=blo,bs=0,j2={};for(var ii=alo;ii<ahi;ii++){var nj={},arr=b2j[a[ii]]||[];for(var x=0;x<arr.length;x++){var j=arr[x];if(j<blo)continue;if(j>=bhi)break;var k=(j2[j-1]||0)+1;nj[j]=k;if(k>bs){bi=ii-k+1;bj=j-k+1;bs=k;}}j2=nj;}return[bi,bj,bs];}var q=[[0,a.length,0,b.length]],bl=[];while(q.length){var c=q.pop(),r=fl(c[0],c[1],c[2],c[3]),pi=r[0],pj=r[1],pk=r[2];if(pk>0){bl.push([pi,pj,pk]);if(c[0]<pi&&c[2]<pj)q.push([c[0],pi,c[2],pj]);if(pi+pk<c[1]&&pj+pk<c[3])q.push([pi+pk,c[1],pj+pk,c[3]]);}}bl.sort(function(x,y){return x[0]-y[0];});bl.push([a.length,b.length,0]);return bl;}
function diverge(R,H){var bl=blocks(R,H),divs=[],ia=0,ib=0,matched=0,i;for(i=0;i<bl.length;i++){var bi=bl[i][0],bj=bl[i][1],bk=bl[i][2];if(bi>ia||bj>ib)divs.push([ia,bi,ib,bj]);ia=bi+bk;ib=bj+bk;matched+=bk;}var mg=[];for(i=0;i<divs.length;i++){var d=divs[i];if(mg.length&&d[0]-mg[mg.length-1][1]<4){mg[mg.length-1][1]=d[1];mg[mg.length-1][3]=d[3];}else mg.push(d.slice());}return{divs:mg,matched:matched};}
function major(rp,hp){if(Math.max(rp.length,hp.length)>=2)return true;var i;for(i=0;i<rp.length;i++)if(NUMSYL.indexOf(rp[i])>=0)return true;for(i=0;i<hp.length;i++)if(NUMSYL.indexOf(hp[i])>=0)return true;return false;}
function mmss(t){if(t==null)return"--:--";var s=Math.floor(t);return("0"+Math.floor(s/60)).slice(-2)+":"+("0"+(s%60)).slice(-2);}
function esc(s){return(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function status(m){var e=document.getElementById('tc-status');if(e)e.textContent=m;}
window.tcSaveKey=function(){var k=((document.getElementById('tc-key')||{}).value||'').trim();if(!k){status('❌ 키를 입력한 뒤 확인을 눌러주세요');return;}try{localStorage.setItem('groqKey',k);}catch(e){}status('✅ 키 저장됨');};
window.tcPick=function(f){if(!f)return;window.__tcFile=f;window.__tcBuf=null;var dt=document.getElementById('tc-drop-text');if(dt)dt.innerHTML='🎧 '+esc(f.name);var au=document.getElementById('tc-audio');if(au){au.src=URL.createObjectURL(f);au.style.display='block';au.ontimeupdate=function(){var c=document.getElementById('tc-cur');if(c)c.textContent=mmss(au.currentTime||0);};}window.__tcManual=[];window.__tcPendingStart=null;var mp=document.getElementById('tc-manual');if(mp)mp.style.display='block';tcRenderManual();try{var rd=new FileReader();rd.onload=function(e){try{getCtx().decodeAudioData(e.target.result,function(b){window.__tcBuf=b;},function(){});}catch(err){}};rd.readAsArrayBuffer(f);}catch(e){}status('음성 선택됨');};
window.tcRun=function(){var key=((document.getElementById('tc-key')||{}).value||'').trim();if(!key){status('❌ Groq API 키를 입력하세요 (console.groq.com/keys)');return;}try{localStorage.setItem('groqKey',key);}catch(e){}var fe=document.getElementById('tc-file'),f=window.__tcFile||(fe&&fe.files&&fe.files[0]);if(!f){status('❌ 음성 파일을 먼저 선택하세요');return;}if(!TTS_REF){status('❌ 원본 TTS 대본이 없어 대조할 수 없습니다');return;}var au=document.getElementById('tc-audio');au.src=URL.createObjectURL(f);au.style.display='block';status('⏳ Groq Whisper로 받아쓰는 중…');var fd=new FormData();fd.append('file',f);fd.append('model','whisper-large-v3');fd.append('language','ko');fd.append('response_format','verbose_json');fd.append('temperature','0');fd.append('timestamp_granularities[]','segment');fd.append('timestamp_granularities[]','word');fetch('https://api.groq.com/openai/v1/audio/transcriptions',{method:'POST',headers:{'Authorization':'Bearer '+key},body:fd}).then(function(r){if(!r.ok)return r.text().then(function(t){throw new Error(r.status+' '+t.slice(0,160));});return r.json();}).then(function(res){render(res);}).catch(function(e){var msg=String(e.message||e);status('❌ 오류: '+msg);});};
function render(res){var words=res.words||[],segs=res.segments||[],full=res.text||'',wordMode=words.length>0,i;var hsrc=wordMode?(function(){var a=[];for(var k=0;k<words.length;k++)a.push({start:+words[k].start||0,text:words[k].word||''});return a;})():(segs.length?segs:[{start:0,text:full}]);var ref=normRef(TTS_REF),hyp=normHyp(hsrc),R=ref.s,H=hyp.s,dz2=diverge(R,H),divs=dz2.divs;var pct=R.length?(dz2.matched/R.length*100):0,badR=[];for(i=0;i<divs.length;i++){var d=divs[i],rp=R.slice(d[0],d[1]),hp=H.slice(d[2],d[3]),flag=(rp.length===0)?(hp.length>=3):(hp.length>=8&&major(rp,hp));if(!flag)continue;if(hyp.tm.length&&d[3]>d[2]){var j1=Math.min(d[2],hyp.tm.length-1),j2=Math.min(d[3]-1,hyp.tm.length-1);badR.push([hyp.tm[j1],hyp.tm[j2]]);}}function isBad(s,e){for(var b=0;b<badR.length;b++){if(s<=badR[b][1]+0.06&&e>=badR[b][0]-0.06)return true;}return false;}var W=[];if(wordMode){for(i=0;i<words.length;i++)W.push({w:(words[i].word||'').trim(),start:+words[i].start||0,end:+words[i].end||0});}else{var sg=segs.length?segs:[{start:0,end:0,text:full}];for(i=0;i<sg.length;i++)W.push({w:(sg[i].text||'').trim(),start:+sg[i].start||0,end:(sg[i].end!=null?+sg[i].end:0)});}for(i=0;i<W.length;i++){W[i].cend=(i+1<W.length)?W[i+1].start:W[i].end;if(W[i].cend<W[i].end)W[i].cend=W[i].end;W[i].bad=isBad(W[i].start,W[i].cend);W[i].del=false;}window.__tcWords=W;var lines=[];if(wordMode&&segs.length){var wi=0;for(var si=0;si<segs.length;si++){var en=(segs[si].end!=null?+segs[si].end:1e9),idxs=[];while(wi<W.length&&W[wi].start<en-0.001){idxs.push(wi);wi++;}if(idxs.length)lines.push({start:W[idxs[0]].start,end:W[idxs[idxs.length-1]].cend,idxs:idxs});}if(wi<W.length){var rem=[];while(wi<W.length){rem.push(wi);wi++;}lines.push({start:W[rem[0]].start,end:W[rem[rem.length-1]].cend,idxs:rem});}}else{for(i=0;i<W.length;i++)lines.push({start:W[i].start,end:W[i].cend,idxs:[i]});}var nbad=0;for(i=0;i<W.length;i++)if(W[i].bad)nbad++;document.getElementById('tc-summary').innerHTML='<b>대본의 '+pct.toFixed(1)+'%</b>가 음성과 일치 \xb7 <span style="color:#ff6a82">오독 의심 '+nbad+'개</span>';var h='<div style="display:flex;gap:8px;margin-bottom:8px"><button onclick="tcBuildTrim()" style="padding:8px 16px;border-radius:7px;border:0;background:#b5462f;color:#fff;font-weight:700;cursor:pointer">✂️ 표시한 부분 빼고 음성 만들기</button><span id="tc-segcount" style="color:#9aa4b2;font-size:13px"></span></div>';for(var li=0;li<lines.length;li++){var ln=lines[li];h+='<div style="display:flex;gap:8px;align-items:flex-start;padding:6px 9px;margin:4px 0;border-radius:7px;border:1px solid #243044;background:#161c28"><span style="color:#67d0ff;font-size:12px;font-weight:700;white-space:nowrap">'+mmss(ln.start)+'</span><button class="tc-lp" data-s="'+ln.start+'" data-e="'+ln.end+'" title="듣기" style="background:none;border:0;color:#9ad;cursor:pointer;font-size:13px">▶</button><div style="flex:1;line-height:2">';for(var x=0;x<ln.idxs.length;x++){var idx=ln.idxs[x],tk=W[idx];h+='<span class="tc-w" data-i="'+idx+'" style="cursor:pointer;padding:1px 4px;border-radius:4px;margin:1px;display:inline-block;'+(tk.del?'background:#9a2540;color:#fff;text-decoration:line-through':(tk.bad?'background:#7a2a3c;color:#ffd0d8;border-bottom:2px solid #ff5a7a;font-weight:700':'color:#dfe4ea'))+'">'+esc(tk.w)+'</span> ';}h+='</div></div>';}var rs=document.getElementById('tc-results');rs.innerHTML=h;document.getElementById('tc-trim').innerHTML='';var au=document.getElementById('tc-audio');[].forEach.call(rs.querySelectorAll('.tc-lp'),function(el){el.addEventListener('click',function(ev){ev.stopPropagation();var s=parseFloat(el.dataset.s),e=parseFloat(el.dataset.e);if(au){au.currentTime=Math.max(0,s);au.play();clearTimeout(window.__tcStop);if(e>s)window.__tcStop=setTimeout(function(){au.pause();},(e-s)*1000+150);}});});var tcLast=-1;[].forEach.call(rs.querySelectorAll('.tc-w'),function(el){el.addEventListener('click',function(ev){ev.stopPropagation();var i=+el.dataset.i,Wd=window.__tcWords;if(ev.shiftKey&&tcLast>=0){var a=Math.min(tcLast,i),b=Math.max(tcLast,i),k;for(k=a;k<=b;k++){Wd[k].del=true;var sp=rs.querySelector('.tc-w[data-i="'+k+'"]');if(sp)tcPaintWord(sp,Wd[k]);}}else{Wd[i].del=!Wd[i].del;tcPaintWord(el,Wd[i]);}tcLast=i;tcSegCount();});});tcSegCount();status('✅ 완료');}
function tcPaintWord(el,t){el.style.background=t.del?'#9a2540':(t.bad?'#7a2a3c':'transparent');el.style.color=t.del?'#fff':(t.bad?'#ffd0d8':'#dfe4ea');el.style.textDecoration=t.del?'line-through':'none';el.style.borderBottom=(t.bad&&!t.del)?'2px solid #ff5a7a':'none';}
function tcSegCount(){var n=0,W=window.__tcWords||[],i;for(i=0;i<W.length;i++)if(W[i].del)n++;var e=document.getElementById('tc-segcount');if(e)e.textContent=n?('🗑 '+n+'개 표시됨'):'믨 부분을 클릭해 표시하세요';}
window.tcBuildTrim=function(){var buf=window.__tcBuf;if(!buf){status('⏳ 음성 디코딩 중...');return;}var W=window.__tcWords||[],D=buf.duration,dels=[],i;for(i=0;i<W.length;i++)if(W[i].del){var ds=Math.max(0,Math.min(+W[i].start,+W[i].cend)),de=Math.min(D,Math.max(+W[i].start,+W[i].cend));if(de>ds)dels.push([ds,de]);}var Mn=window.__tcManual||[];for(i=0;i<Mn.length;i++){var ms=Math.max(0,Math.min(Mn[i][0],Mn[i][1])),me=Math.min(D,Math.max(Mn[i][0],Mn[i][1]));if(me>ms)dels.push([ms,me]);}if(!dels.length){status('❌ 믨 부분을 먼저 표시하세요');return;}dels.sort(function(a,b){return a[0]-b[0];});var md=[];for(i=0;i<dels.length;i++){if(md.length&&dels[i][0]<=md[md.length-1][1]+0.02)md[md.length-1][1]=Math.max(md[md.length-1][1],dels[i][1]);else md.push(dels[i].slice());}var dur=buf.duration,keep=[],cur=0;for(i=0;i<md.length;i++){var a=Math.max(0,md[i][0]),b=Math.min(dur,md[i][1]);if(a>cur)keep.push([cur,a]);cur=Math.max(cur,b);}if(cur<dur)keep.push([cur,dur]);var sr=buf.sampleRate,ch=buf.numberOfChannels,ks=[],total=0;for(i=0;i<keep.length;i++){var s0=Math.round(keep[i][0]*sr),s1=Math.round(keep[i][1]*sr);if(s1>s0){ks.push([s0,s1]);total+=s1-s0;}}if(!total){status('❌ 남는 음성이 없습니다');return;}var actx=getCtx(),out=actx.createBuffer(ch,total,sr);for(var c=0;c<ch;c++){var od=out.getChannelData(c),srcd=buf.getChannelData(c),off=0;for(i=0;i<ks.length;i++){od.set(srcd.subarray(ks[i][0],ks[i][1]),off);off+=ks[i][1]-ks[i][0];}}var cnt=0;for(i=0;i<W.length;i++)if(W[i].del)cnt++;var blob=encodeWAV(out);window.__tcTrimBlob=blob;var url=URL.createObjectURL(blob),secs=0;for(i=0;i<md.length;i++)secs+=md[i][1]-md[i][0];document.getElementById('tc-trim').innerHTML='<div style="margin:10px 0 6px;color:#6fe09a;font-size:14px">✅ '+cnt+'개 부분(약 '+secs.toFixed(1)+'초) 제거 완료</div><audio controls src="'+url+'" style="width:100%"></audio><div style="margin-top:8px;display:flex;gap:8px"><button onclick="tcToSync()" style="padding:9px 18px;border-radius:7px;border:0;background:#2e7d5b;color:#fff;font-weight:700;cursor:pointer">📖 이 음성으로 싱크</button><a href="'+url+'" download="trimmed.wav" style="display:inline-block;padding:9px 18px;border-radius:7px;background:#3a4a63;color:#fff;text-decoration:none;font-weight:700">💾 다운로드</a></div>';status('✅ 정리된 음성 완성');};
window.tcToSync=function(){if(!window.__tcTrimBlob)return;try{mergedBlob=window.__tcTrimBlob;useMergedForSync();showCat('reading');}catch(e){status('❌ '+e);}};
function tcAuTime(){var au=document.getElementById('tc-audio');return au?(au.currentTime||0):0;}
window.tcMarkStart=function(){window.__tcPendingStart=tcAuTime();var p=document.getElementById('tc-pending');if(p)p.textContent='시작 '+mmss(window.__tcPendingStart);};
window.tcMarkEnd=function(){var s=window.__tcPendingStart,e=tcAuTime();if(s==null){status('먼저 "여기부터"를 누르세요');return;}if(e<=s){status('끝 지점이 시작보다 뒤여야 해요');return;}if(!window.__tcManual)window.__tcManual=[];window.__tcManual.push([s,e]);window.__tcPendingStart=null;var p=document.getElementById('tc-pending');if(p)p.textContent='';tcRenderManual();};
function tcRenderManual(){var L=window.__tcManual||[],h='',i;for(i=0;i<L.length;i++){h+='<div style="display:flex;gap:8px;align-items:center;margin:3px 0;color:#ffd0d8;font-size:13px"><span>✂️ '+mmss(L[i][0])+' ~ '+mmss(L[i][1])+'</span><button onclick="tcDelManual('+i+')" style="background:none;border:0;color:#9ad;cursor:pointer">🗑</button></div>';}var e=document.getElementById('tc-manlist');if(e)e.innerHTML=h||'<span style="color:#7a8699;font-size:12px">아직 지정한 구간 없음</span>';}
window.tcDelManual=function(i){if(window.__tcManual)window.__tcManual.splice(i,1);tcRenderManual();};
try{var sk=localStorage.getItem('groqKey');if(sk){var ke=document.getElementById('tc-key');if(ke&&!ke.value)ke.value=sk;}}catch(e){}
var dz=document.getElementById('tc-drop');
if(dz){dz.addEventListener('dragover',function(e){e.preventDefault();dz.style.borderColor='#2e7d5b';});dz.addEventListener('dragleave',function(){dz.style.borderColor='#2c3a52';});dz.addEventListener('drop',function(e){e.preventDefault();dz.style.borderColor='#2c3a52';var f=e.dataTransfer&&e.dataTransfer.files&&e.dataTransfer.files[0];if(f)window.tcPick(f);});}
})();
"""


def generate(meta):
    stock = esc(meta.get('stock_name', ''))
    date = meta.get('date', '')
    keyword = esc(meta.get('keyword', ''))
    phone = meta.get('phone', '01054451634')

    reading = meta.get('reading', '')
    tts = meta.get('tts', '')
    news = meta.get('news', '')
    titles = meta.get('titles', [])
    desc = meta.get('description', '')
    thumb = meta.get('thumbnail_text', '')
    hashtags = meta.get('hashtags', '')
    tags = meta.get('tags', '')

    reading_html = build_reading_html(reading)
    titles_html = build_titles_html(titles)
    news_html = build_news_html(news)

    youtube_raw = '\n'.join([
        '\n'.join(f'{i+1}. {t}' for i, t in enumerate(titles)),
        '', desc, '', thumb, '', hashtags, '', tags
    ])

    raw_json = js({
        'reading': reading,
        'tts': tts,
        'chat0': news,
        'youtube': youtube_raw,
        'audiomerge': '',
        'ttscheck': ''
    })

    tts_ref_js = js(tts)
    stock_js = js(meta.get('stock_name', ''))
    date_js = js(date)

    desc_html = f'<pre class="yt-pre">{esc(desc)}</pre>' if desc else '<p style="color:#888">설명란 데이터 없음</p>'
    thumb_html = f'<pre class="yt-pre">{esc(thumb)}</pre>' if thumb else '<p style="color:#888">썸네일 데이터 없음</p>'
    hashtags_html = f'<pre class="yt-pre">{esc(hashtags)}</pre>' if hashtags else '<p style="color:#888">해시태그 데이터 없음</p>'
    tags_html = f'<pre class="yt-pre">{esc(tags)}</pre>' if tags else '<p style="color:#888">태그 데이터 없음</p>'

    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{stock} | 대본 뷰어</title>
<style>{CSS}</style>
</head>
<body>

<!-- 사이드바 -->
<div class="sidebar">
  <div class="stock-hdr">
    <div class="stock-name">{stock}</div>
    <div class="kw-badge">{keyword}</div>
  </div>
  <button class="nav-btn active" data-cat="reading" onclick="showCat('reading')"><span class="nav-icon">📖</span> 촬영용 대본</button>
  <button class="nav-btn" data-cat="tts" onclick="showCat('tts')"><span class="nav-icon">🔊</span> TTS 대본</button>
  <button class="nav-btn" data-cat="chat0" onclick="showCat('chat0')"><span class="nav-icon">📰</span> 뉴스·공시</button>
  <button class="nav-btn" data-cat="youtube" onclick="showCat('youtube')"><span class="nav-icon">🎬</span> 제목/설명/태그</button>
  <button class="nav-btn" data-cat="audiomerge" onclick="showCat('audiomerge')"><span class="nav-icon">🎵</span> 음성 병합</button>
  <button class="nav-btn" data-cat="ttscheck" onclick="showCat('ttscheck')"><span class="nav-icon">🧪</span> TTS 검증</button>
</div>

<!-- 메인 -->
<div class="main">

<!-- 1. 촬영용 대본 -->
<div class="panel" id="panel-reading">
  <div class="card">
    <div class="bar">
      <span class="title">📖 촬영용 대본</span>
      <div style="display:flex;gap:6px;align-items:center">
        <div class="fz-wrap">
          <button class="fz-btn" onclick="fz(-2)">A-</button>
          <button class="fz-btn" onclick="fz(2)">A+</button>
        </div>
        <button class="copy" onclick="cpRaw('reading')">📋 복사</button>
      </div>
    </div>
    <div class="rbody" id="reading">{reading_html}</div>
    <div class="sync-bar">
      <input type="file" id="sync-file" accept="audio/*" style="display:none" onchange="loadSyncAudio(this)">
      <button class="play-btn" id="syncPlayBtn" disabled onclick="toggleSync()">▶ 싱크 재생</button>
      <button class="stop-btn" onclick="stopSync()">⏹</button>
      <button class="stop-btn" onclick="document.getElementById('sync-file').click()">🎵 음성 선택</button>
      <span class="time-label" id="sync-name">음성 파일을 선택하세요</span>
      <div class="progress-wrap" id="sync-progress" onpointerdown="seekStart(event)">
        <div class="progress-fill" id="sync-fill"></div>
        <div class="progress-knob" id="sync-knob"></div>
      </div>
      <span class="time-label"><span id="sync-cur">0:00</span> / <span id="sync-dur">0:00</span></span>
    </div>
  </div>
</div>

<!-- 2. TTS 대본 -->
<div class="panel" id="panel-tts" style="display:none">
  <div class="card">
    <div class="bar">
      <span class="title">🔊 TTS 대본 (일레븐랩스용)</span>
      <button class="copy" onclick="cpRaw('tts')">📋 복사</button>
    </div>
    <div class="tts-body">{esc(tts) if tts else '<span style="color:#888">TTS 대본 데이터 없음 — validate.py 실행 후 meta.json을 다시 만드세요</span>'}</div>
  </div>
</div>

<!-- 3. 뉴스·공시 -->
<div class="panel" id="panel-chat0" style="display:none">
  <div class="card">
    <div class="bar">
      <span class="title">📰 뉴스·공시</span>
      <button class="copy" onclick="cpRaw('chat0')">📋 복사</button>
    </div>
    <div class="body">{news_html}</div>
  </div>
</div>

<!-- 4. 제목/설명/썸네일/태그 -->
<div class="panel" id="panel-youtube" style="display:none">
  <div class="card">
    <div class="bar">
      <span class="title">🎬 제목 / 설명 / 썸네일 / 태그</span>
      <button class="copy" onclick="cpRaw('youtube')">📋 전체 복사</button>
    </div>
    <div class="body" style="padding:12px">
      <div class="yt-section open">
        <button class="yt-hdr" onclick="toggleYt(this)">제목 ({len(titles)}개)</button>
        <div class="yt-content" style="display:block">{titles_html}</div>
      </div>
      <div class="yt-section">
        <button class="yt-hdr" onclick="toggleYt(this)">설명란</button>
        <div class="yt-content">
          {desc_html}
          <div class="yt-copy-row"><button class="copy-sm" onclick="cpText(this,{js_attr(desc)})">복사</button></div>
        </div>
      </div>
      <div class="yt-section">
        <button class="yt-hdr" onclick="toggleYt(this)">썸네일 문구</button>
        <div class="yt-content">
          {thumb_html}
          <div class="yt-copy-row"><button class="copy-sm" onclick="cpText(this,{js_attr(thumb)})">복사</button></div>
        </div>
      </div>
      <div class="yt-section">
        <button class="yt-hdr" onclick="toggleYt(this)">해시태그</button>
        <div class="yt-content">
          {hashtags_html}
          <div class="yt-copy-row"><button class="copy-sm" onclick="cpText(this,{js_attr(hashtags)})">복사</button></div>
        </div>
      </div>
      <div class="yt-section">
        <button class="yt-hdr" onclick="toggleYt(this)">영상태그</button>
        <div class="yt-content">
          {tags_html}
          <div class="yt-copy-row"><button class="copy-sm" onclick="cpText(this,{js_attr(tags)})">복사</button></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- 5. 음성 병합 -->
<div class="panel dark-panel" id="panel-audiomerge" style="display:none">
  <div class="card">
    <div class="bar"><span class="title">🎵 TTS 음성 병합 (크로스페이드)</span></div>
    <div style="padding:14px 16px;flex:1;overflow-y:auto;min-height:0">
      <p style="color:#9aa4b2;font-size:14px;margin-bottom:12px">TTS 파일 2개를 올리면 크로스페이드로 이어 붙여 줍니다.</p>
      <div style="display:flex;gap:12px;flex-wrap:wrap">
        <div style="flex:1;min-width:200px">
          <div class="drop-zone" id="drop1" onclick="document.getElementById('file1').click()">
            <div style="font-size:22px">🎙️ 1</div>
            <div class="drop-text">TTS 1 파일을 여기에 드래그하거나 클릭</div>
          </div>
          <input type="file" id="file1" accept="audio/*" style="display:none" onchange="loadAudio(1,this)">
          <audio id="audio1" controls style="display:none;width:100%;margin-top:6px"></audio>
          <div id="dur1" style="color:#67d0ff;font-size:13px;margin-top:4px"></div>
        </div>
        <div style="flex:1;min-width:200px">
          <div class="drop-zone" id="drop2" onclick="document.getElementById('file2').click()">
            <div style="font-size:22px">🎙️ 2</div>
            <div class="drop-text">TTS 2 파일을 여기에 드래그하거나 클릭</div>
          </div>
          <input type="file" id="file2" accept="audio/*" style="display:none" onchange="loadAudio(2,this)">
          <audio id="audio2" controls style="display:none;width:100%;margin-top:6px"></audio>
          <div id="dur2" style="color:#67d0ff;font-size:13px;margin-top:4px"></div>
        </div>
      </div>
      <div class="merge-ctrl">
        <label style="color:#9aa4b2;font-size:13px">크로스페이드</label>
        <input type="range" id="xfade" min="0" max="5000" value="1500" style="width:140px">
        <span id="xfade-val" style="color:#67d0ff;font-size:13px">1.5초</span>
        <button class="merge-btn" id="mergeBtn" disabled onclick="mergeAudio()">🔗 병합</button>
        <button style="padding:8px 14px;border:none;border-radius:7px;background:#3a4a63;color:#fff;cursor:pointer;font-size:13px" onclick="resetAll()">↺ 초기화</button>
        <button style="padding:8px 14px;border:none;border-radius:7px;background:#3a4a63;color:#fff;cursor:pointer;font-size:13px" onclick="syncSingle()">📖 1개만 싱크로</button>
      </div>
      <div class="merge-result" id="merge-result" style="display:none">
        <div style="color:#6fe09a;font-size:14px;margin-bottom:8px">병합 결과 <span id="dur-out" style="color:#67d0ff"></span></div>
        <audio id="audio-out" controls style="width:100%"></audio>
        <div style="margin-top:8px;display:flex;gap:8px">
          <button class="dl-btn" onclick="downloadMerged()">💾 다운로드 (WAV)</button>
          <button class="go-sync-btn" onclick="goSync()">📖 촬영용 대본에서 실행하기</button>
        </div>
      </div>
      <div class="merge-status" id="merge-status"></div>
    </div>
  </div>
</div>

<!-- 6. TTS 음성 검증 -->
<div class="panel dark-panel" id="panel-ttscheck" style="display:none">
  <div class="card">
    <div class="bar"><span class="title">🧪 TTS 음성 검증 (오독 찾기)</span></div>
    <div style="padding:14px 16px;flex:1;overflow-y:auto;min-height:0">
      <p class="tc-desc">TTS로 만든 음성을 올리면 다시 받아쓰기 해서 <b>원본 TTS 대본</b>과 대조하고, <b>잘못 읽은 지점</b>을 시간과 함께 짚어줍니다. (Groq Whisper · 키 무료)</p>
      <div class="tc-key-row">
        <input type="password" id="tc-key" placeholder="Groq API 키 (gsk_...) — console.groq.com/keys 무료" class="tc-key-input">
        <button onclick="tcSaveKey()" class="tc-key-btn">확인</button>
      </div>
      <div class="tc-drop" id="tc-drop" onclick="document.getElementById('tc-file').click()">
        <div style="font-size:26px">🎙️</div>
        <div id="tc-drop-text" style="margin-top:5px;font-size:14px;color:#9aa4b2">음성 파일을 여기로 <b style="color:#cdd3dc">끌어다 놓거나</b> 클릭해서 선택</div>
      </div>
      <input type="file" id="tc-file" accept="audio/*" style="display:none" onchange="tcPick(this.files[0])">
      <div style="display:flex;justify-content:flex-end;margin-top:10px">
        <button onclick="tcRun()" class="tc-run-btn">🧪 검증 실행</button>
      </div>
      <audio id="tc-audio" controls style="display:none;width:100%;margin-top:10px"></audio>
      <div id="tc-manual" style="display:none;margin-top:10px;padding:10px 12px;border:1px dashed #2c3a52;border-radius:8px;background:#0e1622">
        <div style="color:#cdd3dc;font-size:13px;margin-bottom:7px">✋ 손으로 자르기</div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <span style="color:#9aa4b2;font-size:12px">재생 위치 <b id="tc-cur" style="color:#67d0ff">0:00</b></span>
          <button onclick="tcMarkStart()" style="padding:7px 13px;border-radius:6px;border:0;background:#3a4a63;color:#fff;font-weight:700;cursor:pointer;font-size:13px">⏱ 여기부터</button>
          <button onclick="tcMarkEnd()" style="padding:7px 13px;border-radius:6px;border:0;background:#b5462f;color:#fff;font-weight:700;cursor:pointer;font-size:13px">⏱ 여기까지</button>
          <span id="tc-pending" style="color:#ffd0d8;font-size:12px"></span>
        </div>
        <div id="tc-manlist" style="margin-top:8px"></div>
      </div>
      <div id="tc-status" style="margin-top:10px;color:#9aa4b2;font-size:13px;min-height:18px"></div>
      <div id="tc-summary" style="margin-top:6px;font-size:14px;color:#cdd3dc"></div>
      <div id="tc-results" style="margin-top:8px"></div>
      <div id="tc-trim"></div>
    </div>
  </div>
</div>

</div><!-- /main -->

<script>
var RAW = {raw_json};
var stockName = {stock_js};
var fileDate = {date_js};
var TTS_REF = {tts_ref_js};
{JS_CORE}
{JS_AUDIO}
{JS_SYNC}
{JS_TTSCHECK}
</script>
</body></html>"""


def read_meta(path):
    """meta.json을 읽되, 없는 필드는 주변 파일에서 보충한다"""
    with open(path, encoding='utf-8') as f:
        meta = json.load(f)

    base = os.path.dirname(os.path.abspath(path))

    if not meta.get('reading'):
        for name in ['대본.txt', 'script.txt']:
            p = os.path.join(base, name)
            if os.path.exists(p):
                with open(p, encoding='utf-8') as f:
                    meta['reading'] = f.read().strip()
                break

    if not meta.get('tts'):
        for name in ['TTS용_대본.txt', 'tts.txt']:
            p = os.path.join(base, name)
            if os.path.exists(p):
                with open(p, encoding='utf-8') as f:
                    meta['tts'] = f.read().strip()
                break

    if not meta.get('news'):
        p = os.path.join(base, 'brief.md')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                text = f.read()
            m = re.search(r'## (?:뉴스|공시|주요 뉴스)(.*?)(?=\n## |\Z)', text, re.DOTALL)
            if m:
                meta['news'] = m.group(1).strip()

    return meta


def main():
    if len(sys.argv) > 1:
        meta_path = sys.argv[1]
    else:
        meta_path = 'meta.json'

    if not os.path.exists(meta_path):
        print(f'❌ {meta_path} 파일을 찾을 수 없습니다.')
        print('사용법: python _tools/render.py [meta.json 경로]')
        sys.exit(1)

    meta = read_meta(meta_path)
    html = generate(meta)

    out_dir = os.path.dirname(os.path.abspath(meta_path))
    out_path = os.path.join(out_dir, 'output.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    abs_path = os.path.abspath(out_path)
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(f'output.html 생성 완료')
    print(f'  -> {abs_path}')

    import webbrowser
    webbrowser.open(f'file:///{abs_path.replace(os.sep, "/")}')


if __name__ == '__main__':
    main()
