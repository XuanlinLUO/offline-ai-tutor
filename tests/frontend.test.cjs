const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function harness(stream, failStatus) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value:'', textContent:'', hidden:false, disabled:false, scrollHeight:20,
      handlers:{}, classList:{toggle(){},remove(){}},
      addEventListener(name, fn){this.handlers[name]=fn;}, focus(){}, removeAttribute(){},
      set innerHTML(_){throw new Error('Unsafe HTML rendering');}
    });
    return elements.get(id);
  }
  const fetch = async (url, options) => {
    if (url === '/api/health') return new Response(JSON.stringify({demo:false, model:{ready:true, message:'ok',model:'test'}}));
    if (failStatus) return new Response(JSON.stringify({error:'模型未就绪'}),{status:failStatus});
    const bytes = new TextEncoder().encode(stream);
    return new Response(new ReadableStream({start(controller){
      // Split through both UTF-8 characters and SSE delimiters.
      for(let i=0;i<bytes.length;i+=7) controller.enqueue(bytes.slice(i,i+7));
      controller.close();
    }}),{headers:{'Content-Type':'text/event-stream'}});
  };
  const context = vm.createContext({document:{getElementById:element},fetch,AbortController,AbortSignal,
    TextDecoder,TextEncoder,setInterval(){},setTimeout(){},navigator:{clipboard:{writeText:async()=>{}}}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/static/app.js'),'utf8'),context);
  return {context,element};
}

test('Chinese SSE survives split UTF-8 and renders as inert text',async()=>{
  const raw = 'data: {"type":"start"}\n\ndata: {"type":"token","content":"中文<script>不可执行</script>"}\n\ndata: {"type":"done","metrics":{"model":"test"}}\n\n';
  const h=harness(raw); await vm.runInContext('health()',h.context);
  await vm.runInContext('setQuestion("题目");generate("题目")',h.context);
  assert.equal(h.element('answer').textContent,'中文<script>不可执行</script>');
  assert.equal(h.element('followup-area').hidden,false);
  assert.equal(vm.runInContext('state.history.length',h.context),2);
});

test('Premature EOF never reports completion or saves a successful turn',async()=>{
  const h=harness('data: {"type":"token","content":"未完成"}\n\n');
  await vm.runInContext('health()',h.context);
  await vm.runInContext('setQuestion("题目");generate("题目")',h.context);
  assert.match(h.element('notice').textContent,/提前结束/);
  assert.equal(h.element('followup-area').hidden,true);
  assert.equal(vm.runInContext('state.history.length',h.context),0);
});

test('Upstream error is visible and busy state is released',async()=>{
  const h=harness('',503); await vm.runInContext('health()',h.context);
  await vm.runInContext('setQuestion("题目");generate("题目")',h.context);
  assert.equal(h.element('notice').textContent,'模型未就绪');
  assert.equal(vm.runInContext('state.busy',h.context),false);
  assert.equal(h.element('ask').disabled,false);
});
