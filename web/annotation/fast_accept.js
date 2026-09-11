'use strict';
(function(root, factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.FastAccept=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const ordinaryClear={
    occluder:'none',
    occlusion:'none',
    visibility:'clear',
    motion_blur:'none',
    annotation_confidence:'certain'
  };

  function inferFocusBox(focusPoint,boxes){
    const [x,y]=focusPoint;
    const containing=boxes.filter(box=>
      x>=box.x1&&x<=box.x2&&y>=box.y1&&y<=box.y2
    );
    if(containing.length===1)return {ok:true,boxId:containing[0].id};
    if(containing.length>1)return {
      ok:false,
      error:'Fast accept needs manual focus review: multiple candidate focus boxes.'
    };
    return {
      ok:false,
      error:'Fast accept needs manual focus review: no unambiguous focus box.'
    };
  }

  function prepareFastAccept(item,dirty){
    if(dirty)return {
      ok:false,
      error:'Frame has unsaved edits. Use Save & Next or undo/reload before fast accept.'
    };
    if(!item)return {ok:false,error:'No frame is loaded.'};

    let focus;
    if(item.priority!==2){
      focus=inferFocusBox(item.focus_point,item.boxes);
      if(!focus.ok)return focus;
    }

    const prepared=JSON.parse(JSON.stringify(item));
    prepared.boxes=prepared.boxes.map(box=>Object.assign(box,ordinaryClear));
    prepared.all_visible_confirmed=true;
    if(prepared.priority===2){
      prepared.focus_status='not_applicable';
      prepared.focus_box_id=null;
    }else{
      prepared.focus_status='visible';
      prepared.focus_box_id=focus.boxId;
    }
    return {ok:true,item:prepared};
  }

  async function runFastAccept({item,dirty,save,message}){
    const result=prepareFastAccept(item,dirty);
    if(!result.ok){
      message(result.error);
      return false;
    }
    await save('completed',true,result.item);
    return true;
  }

  return {inferFocusBox,prepareFastAccept,runFastAccept};
});
