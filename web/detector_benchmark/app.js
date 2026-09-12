'use strict';
const $=id=>document.getElementById(id);
let data,index=0,visible=[];
function arms(){return Object.keys(data.arms);}
function matches(row){
  const source=$('sourceFilter').value,kind=$('kindFilter').value;
  const regionMatch=source==='all'||(source==='overlap'&&!row.selection.endsWith('_only'))||row.selection===source;
  return regionMatch&&(kind==='all'||row.provenance.some(p=>p.event_kind===kind));
}
function initPanels(){
  $('panels').replaceChildren(...arms().map(arm=>{
    const section=document.createElement('section'),heading=document.createElement('h2'),canvas=document.createElement('canvas');
    heading.textContent=data.arms[arm].label;canvas.id=`canvas-${arm}`;section.append(heading,canvas);return section;
  }));
}
function draw(canvas,image,detections,color){
  canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
  const c=canvas.getContext('2d');c.drawImage(image,0,0);
  c.strokeStyle=color;c.fillStyle=color;c.lineWidth=Math.max(2,canvas.width/700);c.font=`${Math.max(13,canvas.width/90)}px system-ui`;
  for(const d of detections){
    c.strokeRect(d.x1,d.y1,d.x2-d.x1,d.y2-d.y1);
    c.fillText(Number(d.confidence).toFixed(2),d.x1,Math.max(14,d.y1-3));
  }
}
function refilter(keepFrame){
  visible=data.frames.filter(matches);
  index=Math.max(0,visible.findIndex(row=>row.frame===keepFrame));
  if(index<0)index=0;
  render();
}
function render(){
  if(!visible.length){$('meta').textContent='No frames match these filters.';return;}
  const row=visible[index],image=new Image();
  image.onload=()=>arms().forEach((arm,n)=>draw($(`canvas-${arm}`),image,row.detections[arm],['#55e58a','#ffbd69','#63edff'][n%3]));
  image.src=`/frame?frame=${row.frame}`;
  const events=row.provenance.map(p=>`${p.model_arm}:${p.event_kind}@${p.event_frame}`).join(', ');
  $('meta').textContent=`Frame ${row.frame} · ${row.timestamp.toFixed(3)} s · segment ${row.segment.index} · selected: ${row.selection} · ${events} · ${index+1}/${visible.length}`;
  const centers=[...new Set(row.provenance.map(p=>p.event_frame))].sort((a,b)=>a-b);
  $('context').replaceChildren(...centers.flatMap(center=>{
    const label=document.createElement('span');label.textContent=`Event ${center}:`;
    return [label,...data.frames.filter(candidate=>candidate.provenance.some(p=>p.event_frame===center)).map(candidate=>{
      const button=document.createElement('button');button.textContent=(candidate.frame-center>=0?'+':'')+(candidate.frame-center);button.className=candidate.frame===row.frame?'active':'';button.onclick=()=>{index=visible.findIndex(x=>x.frame===candidate.frame);if(index<0){$('sourceFilter').value='all';$('kindFilter').value='all';refilter(candidate.frame);}else render();};return button;
    })];
  }));
}
function step(delta){if(visible.length){index=Math.max(0,Math.min(visible.length-1,index+delta));render();}}
function eventStep(delta){
  if(!visible.length)return;
  const centers=[...new Set(visible.flatMap(row=>row.provenance.map(p=>p.event_frame)))].sort((a,b)=>a-b),current=visible[index].frame;
  const target=delta>0?centers.find(x=>x>current):centers.toReversed().find(x=>x<current);
  if(target!==undefined){const found=visible.findIndex(row=>row.frame===target);if(found>=0){index=found;render();}}
}
$('prev').onclick=()=>step(-1);$('next').onclick=()=>step(1);$('prevEvent').onclick=()=>eventStep(-1);$('nextEvent').onclick=()=>eventStep(1);
$('sourceFilter').onchange=()=>refilter(visible[index]?.frame);$('kindFilter').onchange=()=>refilter(visible[index]?.frame);
document.addEventListener('keydown',event=>{if(['INPUT','SELECT','BUTTON'].includes(event.target.tagName))return;const actions={arrowleft:()=>step(-1),arrowright:()=>step(1),j:()=>eventStep(-1),k:()=>eventStep(1)};const action=actions[event.key.toLowerCase()];if(action){event.preventDefault();action();}});
fetch('/api/data').then(response=>response.json()).then(value=>{data=value;initPanels();refilter();}).catch(error=>{$('meta').textContent=error.message;});
