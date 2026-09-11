'use strict';
const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';
const surveys={
  occluder:['none','hand','body','other_object','mixed'],occlusion:['none','slight','moderate','heavy'],visibility:['clear','partial','tiny_fragment'],motion_blur:['none','mild','strong'],annotation_confidence:['certain','uncertain']
};
const state={
  items:[],item:null,selected:null,dirty:false,mode:'select',addStage:null,drag:null,busy:false,category:''
};
const clone=x=>JSON.parse(JSON.stringify(x));
function fit(){
  if(!state.item)return;
  const s=state.item.source;
  $('canvas').setAttribute('viewBox',Object.values(AnnotationViewport.fitViewBox(s.width,s.height)).join(' '));
}
function zoomTo(point){
  const s=state.item.source;
  const box=AnnotationViewport.zoomViewBox(s.width,s.height,point.x,point.y,4);
  $('canvas').setAttribute('viewBox',Object.values(box).join(' '));
}
function setBusy(value){
  state.busy=value;
  for(const node of document.querySelectorAll('main,nav,details')) node.inert=value;
}
function message(text){
  $('message').textContent=text;
} async function api(path,body){
  const r=await fetch(path,body?{
    method:'POST',headers:{
      'Content-Type':'application/json'
    },body:JSON.stringify(body)
  }:{
  });
  const d=await r.json();
  if(!r.ok)throw Error(d.error||r.statusText);
  return d;
} function changed(){
  state.dirty=true;
  message('Unsaved changes');
} function selected(){
  return state.item?.boxes.find(b=>b.id===state.selected);
} function guard(){
  return !state.dirty||confirm('Discard unsaved changes? Use Save draft to keep incomplete work.');
} function frameURL(t,crop=false){
  return `/frame?id=${state.item.id}&frame=${t}&crop=${crop?1:0}`;
} function filtered(){
  return state.items.filter(i=>state.category===''||String(i.priority)===state.category);
} async function refresh(){
  const d=await api('/api/items');
  state.items=d.items;
  const completed=state.items.filter(i=>i.status==='completed').length;
  const remaining=state.items.filter(i=>i.status==='pending').length;
  $('progress').textContent=`${completed} completed · ${remaining} remaining`;
  const j=$('jump');
  j.replaceChildren();
  for(const i of filtered()){
    const o=new Option(`${i.frame} · ${i.status} · ${i.source_id.slice(0,6)}`,i.id);
    j.add(o);
  }if(state.item)j.value=state.item.id;
} async function load(id,force=false){
  if(state.busy||(!force&&!guard()))return;
  setBusy(true);
  try{
    state.item=await api('/api/item?id='+id);
    state.selected=null;
    state.mode='select';
    state.addStage=null;
    state.drag=null;
    state.dirty=false;
    const d=state.item,s=d.source;
    $('source').textContent=`${s.video_path} · frame ${d.frame} · ${d.timestamp.toFixed(3)} s · ${s.fps.toFixed(3)} FPS · ${d.status}`;
    fit();
    $('raw').setAttribute('href',frameURL(d.frame));
    $('raw').setAttribute('width',s.width);
    $('raw').setAttribute('height',s.height);

    $('focus').value=d.focus_status;
    $('notes').value=d.notes;
    $('completeCheck').checked=d.all_visible_confirmed;
    $('focus').disabled=d.priority===2;
    for(const o of $('focus').options)o.disabled=d.priority===2?o.value!=='not_applicable':o.value==='not_applicable';
    $('filmstrip').replaceChildren();
    const seg=d.segment;
    const bounds=seg?[Math.max(0,Math.ceil(seg.start*s.fps)),Math.min(s.frame_count,Math.ceil(seg.end*s.fps))]:[0,s.frame_count];
    const frames=[...new Set([-8,-4,-2,0,2,4,8].map(x=>Math.max(bounds[0],Math.min(bounds[1]-1,d.frame+Math.round(x*s.fps/60)))) )];
    for(const t of frames){
      const b=document.createElement('button');
      b.className=t===d.frame?'target':'';
      const img=document.createElement('img');
      img.src=frameURL(t);
      img.alt='Raw frame '+t;
      b.append(img,document.createTextNode(`Frame ${t}${t===d.frame?' · TARGET':''}`));
      b.onclick=()=>{
        $('contextImage').src=frameURL(t);
        $('contextLabel').textContent=`Read-only frame ${t}. Annotation target remains ${d.frame}.`;
        $('contextDialog').showModal();
      };
      $('filmstrip').append(b);
    }render();
    $('jump').value=id;
    message('Check every visible ball, fix boxes if needed, then Accept & Next.');
  }catch(e){
    message(e.message);
  }finally{
    setBusy(false);
    render();
  }
} function svg(tag,attrs){
  const el=document.createElementNS(NS,tag);
  for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);
  return el;
} function render(){
  if(!state.item)return;
  const d=state.item,g=$('overlays');
  g.replaceChildren();
  $('mode').textContent=state.mode!=='add'?'Select / move / resize':state.addStage==='pick-center'?'Tap near the missing ball':'Drag to draw the missing ball';
  $('guidance').textContent=d.provenance.map(p=>`${p.event_key} · ${p.kind} · END Δ${p.distance_from_end??'—'} · START Δ${p.distance_from_start??'—'}${p.inside_gap?' · gap':''}`).join(' | ');
  const transform=$('canvas').getScreenCTM();
  const unitX=transform?.a?1/Math.abs(transform.a):1,unitY=transform?.d?1/Math.abs(transform.d):1;
  for(const b of d.boxes){
      const active=b.id===state.selected,color=active?'#63edff':'#55e58a';
      const rect=svg('rect',{
        x:b.x1,y:b.y1,width:b.x2-b.x1,height:b.y2-b.y1,fill:'transparent',stroke:color,'stroke-width':3,'vector-effect':'non-scaling-stroke','data-id':b.id,class:'box'
      });
      g.append(rect);
      const text=svg('text',{
        x:b.x1,y:Math.max(14,b.y1-5),fill:color,'font-size':14,'paint-order':'stroke',stroke:'#000','stroke-width':2,'pointer-events':'none'
      });
      text.textContent=shortId(b);
      g.append(text);
      if(active){
        const points=[['nw',b.x1,b.y1],['n',(b.x1+b.x2)/2,b.y1],['ne',b.x2,b.y1],['e',b.x2,(b.y1+b.y2)/2],['se',b.x2,b.y2],['s',(b.x1+b.x2)/2,b.y2],['sw',b.x1,b.y2],['w',b.x1,(b.y1+b.y2)/2]];
        for(const [handle,x,y]of points){
          g.append(svg('rect',{x:x-15*unitX,y:y-15*unitY,width:30*unitX,height:30*unitY,fill:'transparent','data-id':b.id,'data-handle':handle,class:'handle-hit'}));
          g.append(svg('rect',{x:x-5*unitX,y:y-5*unitY,width:10*unitX,height:10*unitY,fill:color,stroke:'#071014','stroke-width':1,'vector-effect':'non-scaling-stroke','pointer-events':'none'}));
        }
      }
  } $('boxlist').replaceChildren();
  for(const b of d.boxes){
    const el=document.createElement('button');
    el.textContent=shortId(b);
    el.className=b.id===state.selected?'active':'';
    el.onclick=()=>{
      state.selected=b.id;
      render();
    };
    $('boxlist').append(el);
  }const b=selected();
  $('selected').textContent=b?`Ball ${shortId(b)} · ${b.annotation_source}`:'Select a ball box';
  for(const k of Object.keys(surveys)){
    $(k).value=b?.[k]||'';
    $(k).disabled=!b;
  }for(const id of ['preset','delete','focusBox'])$(id).disabled=!b||state.busy;
  $('focusBox').disabled=!b||d.priority===2;
  $('focusId').replaceChildren(new Option('Unknown / none',''));
  for(const box of d.boxes)$('focusId').add(new Option(shortId(box),box.id));
  $('focusId').value=d.focus_box_id||'';
  $('focusId').disabled=d.focus_status!=='visible';
} function shortId(b){
  return 'B'+(state.item.boxes.indexOf(b)+1)+' · '+b.id.slice(-5);
} function point(e){
  const m=$('canvas').getScreenCTM().inverse(),p=new DOMPoint(e.clientX,e.clientY).matrixTransform(m),s=state.item.source;
  return {
    x:Math.max(0,Math.min(s.width,p.x)),y:Math.max(0,Math.min(s.height,p.y))
  };
} $('canvas').addEventListener('pointerdown',e=>{
  if(!state.item||state.busy||e.button!==0)return;
  e.preventDefault();
  $('canvas').focus();
  const p=point(e),id=e.target.getAttribute('data-id'),handle=e.target.getAttribute('data-handle');
  const before=clone(state.item.boxes),dirty=state.dirty;
  if(state.mode==='add'){
    if(state.addStage==='pick-center'){
      zoomTo(p);
      state.addStage='draw';
      render();
      message('Drag to draw the missing ball');
      return;
    }
    const id=AnnotationHelpers.newManualBoxId(state.item.boxes);
    state.item.boxes.push({
      id,x1:p.x,y1:p.y,x2:p.x,y2:p.y,annotation_source:'manual',prediction_id:null,...Object.fromEntries(Object.keys(surveys).map(k=>[k,'']))
    });
    state.selected=id;
    state.drag={
      type:'draw',p,before,dirty,pointerId:e.pointerId
    };
  }else if(id){
    state.selected=id;
    state.drag={
      type:handle||'move',p,box:clone(selected()),before,dirty,pointerId:e.pointerId
    };
  }else{
    state.selected=null;
  }if(state.drag)$('canvas').setPointerCapture(e.pointerId);
  render();
});
$('canvas').addEventListener('pointermove',e=>{
  const d=state.drag,b=selected();
  if(!d||!b||d.pointerId!==e.pointerId)return;
  const p=point(e),s=state.item.source;
  if(d.type==='draw'){
    b.x1=Math.min(d.p.x,p.x);
    b.y1=Math.min(d.p.y,p.y);
    b.x2=Math.max(d.p.x,p.x);
    b.y2=Math.max(d.p.y,p.y);
  }else if(d.type==='move'){
    const dx=Math.max(-d.box.x1,Math.min(s.width-d.box.x2,p.x-d.p.x)),dy=Math.max(-d.box.y1,Math.min(s.height-d.box.y2,p.y-d.p.y));
    for(const k of ['x1','x2'])b[k]=d.box[k]+dx;
    for(const k of ['y1','y2'])b[k]=d.box[k]+dy;
  }else{
    if(d.type.includes('w'))b.x1=Math.min(p.x,b.x2-1);
    if(d.type.includes('e'))b.x2=Math.max(p.x,b.x1+1);
    if(d.type.includes('n'))b.y1=Math.min(p.y,b.y2-1);
    if(d.type.includes('s'))b.y2=Math.max(p.y,b.y1+1);
  }render();
});
function cancel(){
  if(state.drag){
    state.item.boxes=state.drag.before;
    state.dirty=state.drag.dirty;
  }state.drag=null;
  state.mode='select';
  state.addStage=null;
  fit();
  render();
} $('canvas').addEventListener('pointercancel',cancel);
$('canvas').addEventListener('pointerup',e=>{
  if(!state.drag||state.drag.pointerId!==e.pointerId)return;
  const b=selected();
  if(b.x2-b.x1<1||b.y2-b.y1<1){
    cancel();
    return;
  }state.drag=null;
  state.mode='select';
  state.addStage=null;
  fit();
  changed();
  render();
});
function remove(){
  if(!selected()||state.busy)return;
  const id=state.selected;
  state.item.boxes=state.item.boxes.filter(b=>b.id!==id);
  if(state.item.focus_box_id===id)state.item.focus_box_id=null;
  state.selected=null;
  changed();
  render();
} async function navigate(delta){
  const list=filtered(),idx=list.findIndex(i=>i.id===state.item?.id),next=list[idx+delta];
  if(next)await load(next.id);
  else message('End of this category. No automatic wrap or advance.');
} async function save(status,next=false,item=state.item){
  if(!state.item||state.busy||state.drag)return;
  setBusy(true);
  try{
    const payload={
      ...item,status
    };
    state.item=await api('/api/save',payload);
    state.dirty=false;
    await refresh();
    render();
    message('Saved · '+status);
  }catch(e){
    message(e.message);
    return;
  }finally{
    setBusy(false);
    render();
  }if(next){
    const list=filtered(),idx=list.findIndex(i=>i.id===state.item.id);
    const following=[...list.slice(idx+1),...list.slice(0,idx)].find(i=>i.status==='pending');
    if(following)await load(following.id,true);
    else message('Saved. No pending items left in this category.');
  }
} for(const [key,values]of Object.entries(surveys)){
  const label=document.createElement('label');
  label.textContent=key.replaceAll('_',' ');
  const sel=document.createElement('select');
  sel.id=key;
  sel.add(new Option('Choose…',''));
  values.forEach(v=>sel.add(new Option(v,v)));
  sel.onchange=()=>{
    if(selected()){
      selected()[key]=sel.value;
      changed();
      render();
    }
  };
  label.append(sel);
  $('survey').append(label);
} $('preset').onclick=()=>{
  const b=selected();
  if(b){
    Object.assign(b,{
      occluder:'none',occlusion:'none',visibility:'clear',motion_blur:'none',annotation_confidence:'certain'
    });
    changed();
    render();
  }
};
$('focusBox').onclick=()=>{
  if(selected()){
    state.item.focus_status='visible';
    state.item.focus_box_id=state.selected;
    $('focus').value='visible';
    changed();
    render();
  }
};
$('focus').onchange=()=>{
  state.item.focus_status=$('focus').value;
  if(state.item.focus_status!=='visible')state.item.focus_box_id=null;
  changed();
  render();
};
$('focusId').onchange=()=>{
  state.item.focus_box_id=$('focusId').value||null;
  changed();
  render();
};
$('notes').oninput=()=>{
  state.item.notes=$('notes').value;
  changed();
};
$('completeCheck').onchange=()=>{
  state.item.all_visible_confirmed=$('completeCheck').checked;
  changed();
};
$('add').onclick=()=>{
  if(state.item){
    Object.assign(state,AnnotationViewport.startAdd());
    render();
    $('canvas').focus();
    message('Tap near the missing ball');
  }
};
$('delete').onclick=remove;
$('fit').onclick=()=>{
  fit();
  render();
};
$('prev').onclick=()=>navigate(-1);
$('next').onclick=()=>navigate(1);
$('reload').onclick=()=>{
  if(state.item&&(!state.dirty||confirm('Discard edits and reload this frame?')))load(state.item.id,true);
};
$('save').onclick=()=>save('pending');
$('fastAccept').onclick=()=>FastAccept.runAccept({item:state.item,save});
$('skip').onclick=()=>save('skipped',true);
$('closeContext').onclick=()=>$('contextDialog').close();
$('jump').onchange=()=>load($('jump').value);
$('category').onchange=async()=>{
  if(!guard()){
    $('category').value=state.category;
    return;
  }state.category=$('category').value;
  state.dirty=false;
  await refresh();
  const first=filtered().find(i=>i.status==='pending')||filtered()[0];
  if(first)await load(first.id,true);
};
document.addEventListener('keydown',e=>{
  if(e.ctrlKey||e.metaKey||e.altKey||e.repeat||state.busy||$('contextDialog').open)return;
  if(['INPUT','SELECT','TEXTAREA','BUTTON'].includes(e.target.tagName)||e.target.isContentEditable)return;
  const key=e.key.toLowerCase();
  const actions={
    n:()=>navigate(1),arrowright:()=>navigate(1),p:()=>navigate(-1),arrowleft:()=>navigate(-1),a:()=>$('add').click(),delete:remove,backspace:remove,enter:()=>$('fastAccept').click(),g:()=>$('fastAccept').click(),escape:cancel
  };
  if(actions[key]){
    e.preventDefault();
    actions[key]();
  }
});
window.addEventListener('beforeunload',e=>{
  if(state.dirty){
    e.preventDefault();
    e.returnValue='';
  }
});
(async()=>{
  try{
    await refresh();
    const first=state.items.find(i=>i.status==='pending')||state.items[0];
    if(first)await load(first.id,true);
    else message('No mined items. Run the mine command first.');
  }catch(e){
    message(e.message);
  }
})();
