'use strict';
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.FastAccept=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  function prepareAccept(item){
    if(!item)throw Error('No frame is loaded.');
    const prepared=JSON.parse(JSON.stringify(item));
    prepared.all_visible_confirmed=true;
    return prepared;
  }

  async function runAccept({item,save}){
    await save('completed',true,prepareAccept(item));
    return true;
  }

  return {prepareAccept,runAccept};
});
