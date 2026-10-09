const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const root=path.resolve(__dirname,'..'),Vue=require(root+'/node_modules/vue'),{renderToString}=require(root+'/node_modules/@vue/server-renderer'),{parse,compileScript}=require(root+'/node_modules/@vue/compiler-sfc');
const {descriptor}=parse(fs.readFileSync(root+'/src/views/invoice/Form.vue','utf8'));
let source=compileScript(descriptor,{id:'InvoiceQA',inlineTemplate:true,genDefaultAs:'Invoice'}).content.replace(/^import \{([\s\S]*?)\} from ["']vue["']\s*$/gm,(_,s)=>`const {${s.replace(/\bas\b/g,':')}}=Vue`).replace(/^import[\s\S]*?from ["'][^"']+["']\s*$/gm,'');
source=source.replace('return (_ctx, _cache) => {','loading.value=false;fillForm(window.fixture);window.saveEmployee=saveEmployee;return (_ctx, _cache) => {')+';globalThis.Invoice=Invoice;';
async function scenario(method){
 const fixture={name:'Synthetic',status:'Draft',calculation_method:method,currency:'USD',period_start:'2026-09-01',period_end:'2026-09-30',worked_hours:169,paid_holiday_hours:8,system_total_hours:177,payable_hours:177,use_hours_override:1,employee_total_hours:177,hours_override_reason:'Correction',can_employee_edit:true,is_employee_owner:true,adjustments:[],time_summary:[]};
 const calls=[],stub={setup(p,{slots}){return()=>Vue.h('div',{},slots.default?.())}};
 const ctx={Vue,window:{fixture},useRouter:()=>({}),IonPage:stub,IonContent:stub,Button:stub,FeatherIcon:stub,formatHours:n=>`${n} hours`,call:async(method,args)=>{calls.push({method,args});return fixture},console};
 vm.createContext(ctx);vm.runInContext(source,ctx);
 const app=Vue.createSSRApp(ctx.Invoice,{id:'Synthetic'});app.provide('$translate',s=>s);app.provide('$user',{data:{roles:[]}});
 const html=await renderToString(app);
 assert(html.includes('Paid holiday hours'));assert(html.includes('System total hours'));assert(html.includes('Reason for proposed total'));assert(html.includes('169 hours'));assert(html.includes('177 hours'));
 assert.equal(html.includes('Scheduled hours for monthly leave deduction'),method==='Fixed Monthly');
 await ctx.window.saveEmployee();assert.equal(calls[0].args.values.employee_total_hours,177);assert.equal(calls[0].args.values.hours_override_reason,'Correction');assert.equal(calls[0].args.values.use_hours_override,1);
}
(async()=>{await scenario('Hourly');await scenario('Fixed Monthly');console.log('Invoice UI: separate totals, holiday credit, proposal and save payload passed')})().catch(e=>{console.error(e);process.exitCode=1});
