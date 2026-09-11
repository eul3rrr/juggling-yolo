'use strict';
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.AnnotationViewport=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const clamp=(value,min,max)=>Math.min(Math.max(value,min),max);

  function fitViewBox(sourceWidth,sourceHeight){
    return {x:0,y:0,width:sourceWidth,height:sourceHeight};
  }

  function zoomViewBox(sourceWidth,sourceHeight,centerX,centerY,zoom=4){
    const safeZoom=Math.max(1,Number(zoom)||1);
    const width=sourceWidth/safeZoom;
    const height=sourceHeight/safeZoom;
    return {
      x:clamp(centerX-width/2,0,sourceWidth-width),
      y:clamp(centerY-height/2,0,sourceHeight-height),
      width,
      height
    };
  }

  function startAdd(){
    return {mode:'add',addStage:'pick-center'};
  }

  function pickAddCenter(sourceWidth,sourceHeight,point,zoom=4){
    return {mode:'add',addStage:'draw',viewBox:zoomViewBox(sourceWidth,sourceHeight,point[0],point[1],zoom)};
  }

  return {fitViewBox,zoomViewBox,startAdd,pickAddCenter};
});
