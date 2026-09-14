const mode=new URL(location.href).searchParams.get('mode')==='reference'?'reference':'src';
const {readFeature}=await import('/labs/05-faults/'+mode+'/index.js');
const response=await fetch('./api/config');
const config=await response.json();
report('config',{release:response.headers.get('X-Release-Id'),schema:config.schema});
const enabled=readFeature(config);
document.getElementById('app').textContent=enabled?'运营台已启动：库存功能启用':'运营台已启动：库存功能关闭';
report('ready',{enabled});
