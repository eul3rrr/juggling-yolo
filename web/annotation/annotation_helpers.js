'use strict';
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.AnnotationHelpers=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  function newManualBoxId(boxes){
    const existing=new Set(boxes.map(box=>box.id));
    let number=1;
    while(existing.has(`manual-${number}`))number+=1;
    return `manual-${number}`;
  }

  return {newManualBoxId};
});
