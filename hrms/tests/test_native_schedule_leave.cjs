const vm=require('vm'),fs=require('fs'),assert=require('assert'),path=require('path');
const root=path.resolve(__dirname,'..');
let settings,confirmation;const events=[];const frappe={ui:{form:{on:(_,handlers)=>settings=handlers}},user:{has_role:()=>false},confirm:(_,fn)=>confirmation=fn,call:async opts=>events.push('api'),show_alert:()=>events.push('alert'),listview_settings:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,'hr/doctype/employee_schedule/employee_schedule.js'),'utf8'),{frappe,__:s=>s});
function make(status,dirty,fail=false){return {doc:{status,name:'SCH-1'},clear_custom_buttons(){},is_new:()=>false,is_dirty:()=>dirty,add_custom_button(label,fn){this.submit=fn;return {addClass(){}};},set_df_property(){},set_value:async function(field,value){this.doc[field]=value;events.push('status:'+value);},save:async function(){events.push('save:'+this.doc.status);if(fail)throw Error('save failed');},reload_doc:async()=>events.push('reload')};}
(async()=>{
for(const status of ['Draft','Rejected','Approved'])for(const dirty of [true,false]){events.length=0;const frm=make(status,dirty);settings.set_action_buttons(frm);frm.submit();await confirmation();if(dirty){assert(events.some(e=>e.startsWith('save:')));assert(events.indexOf(events.find(e=>e.startsWith('save:')))<events.indexOf('reload'));}if(status==='Approved'&&dirty){assert(events.includes('save:Submitted'));assert(!events.includes('api'));}else assert(events.includes('api'));if(status==='Rejected'&&dirty)assert(events.includes('save:Draft'));}
events.length=0;const frm=make('Approved',true,true);settings.set_action_buttons(frm);frm.submit();await assert.rejects(confirmation());assert.equal(frm.doc.status,'Approved');assert(!events.includes('api'));
vm.runInNewContext(fs.readFileSync(path.join(root,'hr/doctype/leave_application/leave_application_list.js'),'utf8'),{frappe,__:s=>s});
const indicator=frappe.listview_settings['Leave Application'].get_indicator;
assert.equal(indicator({status:'Approved',docstatus:0})[0],'Approved · Awaiting confirmation');assert.equal(indicator({status:'Rejected',docstatus:0})[0],'Rejected · Awaiting confirmation');assert.equal(indicator({status:'Approved',docstatus:1})[0],'Approved');
console.log('Native schedule dirty save/status transitions/failure restore and leave draft decision labels passed');
})().catch(e=>{console.error(e);process.exit(1)});
