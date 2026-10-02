// Component-only visual regression: synthetic projects, no production API writes.
const fs = require('node:fs');
const path = require('node:path');
const { parse, compileScript } = require('@vue/compiler-sfc');
const runtime = process.env.PLAYWRIGHT_MODULE || 'playwright';
const { chromium } = require(runtime);
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'frontend/src/views/timesheet/Timer.vue'), 'utf8');
const { descriptor } = parse(source);
let script = compileScript(descriptor, { id: 'timer', inlineTemplate: true, genDefaultAs: 'TimerComponent' }).content;
script = script.replace(/^import \{([^}]+)\} from ['"]vue['"]/gm, (_, items) => `const {${items.replace(/\bas\b/g, ':')}}=window.Vue`).replace(/^import .*$/gm, '');
const vue = fs.readFileSync(require.resolve('vue/dist/vue.global.prod.js'), 'utf8');
const dayjs = fs.readFileSync(require.resolve('dayjs/dayjs.min.js'), 'utf8');
const assetDir = path.join(root, 'hrms/public/frontend/assets');
const css = fs.readdirSync(assetDir).filter(f => /^index-.*\.css$/.test(f)).map(f => fs.readFileSync(path.join(assetDir, f), 'utf8')).join('\n');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const mocks = `const state={revision:0,initialized:true,server_now:new Date().toISOString(),favorites:['Alpha','Beta'],timer:{startTime:null,form:{project:'',activity_type:'',description:''},segments:[],isPaused:false}};
const call=async(method,args)=>{
 if(method.includes('search_employee_projects'))return [['Alpha','HR System'],['Beta','Platform Development']];
 if(method.endsWith('apply_action')){
 const p=JSON.parse(args.payload),t=state.timer;
 if(['start','switch','resume'].includes(args.action)){if(t.startTime)t.segments.push({project:t.form.project,seconds:1,from:t.startTime,to:new Date().toISOString()});t.form={project:p.project,activity_type:'',description:''};t.startTime=new Date().toISOString();t.isPaused=false;}
 if(args.action==='pause'){t.startTime=null;t.isPaused=true;}state.revision++;
 }state.server_now=new Date().toISOString();return JSON.parse(JSON.stringify(state));
};
const onIonViewWillEnter=()=>{},onIonViewWillLeave=()=>{};
Object.defineProperty(window.crypto,'randomUUID',{value:()=>String(Date.now())+'_'+Math.random().toString(16).slice(2)});
const toast=()=>{},unreadNotificationsCount={reload:async()=>{}},STORAGE_KEY='timer',TIMER_NOTIFIED_KEY='notified';
const FormField={props:['label','modelValue'],emits:['update:modelValue'],template:'<label class="text-gray-700 text-sm">{{label}}<input type="text" :value="modelValue" class="block w-full border rounded p-2 mt-1" @input="$emit(\\'update:modelValue\\',$event.target.value)"></label>'};
const FeatherIcon={props:['name'],template:'<span aria-hidden="true" class="inline-block">*</span>'};
const IonPage={template:'<div><slot/></div>'},IonContent={template:'<div><slot/></div>'};
const storage=new Map([['hrms_favorite_projects',JSON.stringify([{name:'Alpha',label:'HR System'},{name:'Beta',label:'Platform Development'}])]]);
Object.defineProperty(window,'localStorage',{value:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)}});`;
    await page.setContent(`<html><head><style>${css}</style></head><body><div id="app"></div><script>${vue}</script><script>${dayjs}</script><script>${mocks}\n${script}\nconst app=Vue.createApp(TimerComponent);app.provide('$translate',s=>s);app.provide('$employee',{data:{name:'EMP',user_id:'qa@example.test'}});app.provide('$dayjs',dayjs);app.mount('#app');</script></body></html>`);
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 844 });
      for (const dark of [false, true]) {
        await page.evaluate(d => document.documentElement.classList.toggle('dark', d), dark);
        await page.screenshot({ path: `/tmp/hrms-timer-${width}-${dark ? 'dark' : 'light'}.png`, fullPage: true });
        if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw Error(`Timer overflow at ${width}`);
      }
    }
    if (errors.length) throw Error(errors.join('\n'));
    await page.getByRole('button', { name: 'Start', exact: true }).first().click();
    await page.getByRole('button', { name: 'Switch', exact: true }).click();
    if (await page.getByRole('button', { name: 'Pause', exact: true }).count() !== 1) throw Error('Expected one recording project');
    const nativeCss = fs.readFileSync(path.join(root, 'frontend/src/theme/variables.css'), 'utf8');
    await page.setContent(`<html class="dark"><head><style>${nativeCss}</style></head><body style="background:#101010;padding:24px;color:white"><input type="time" value="17:00" style="height:32px;width:90%"><input type="time" value="09:00" disabled style="height:32px;width:90%;margin-top:12px"></body></html>`);
    const colors = await page.locator('input').evaluateAll(els => els.map(el => ({ background: getComputedStyle(el).backgroundColor, color: getComputedStyle(el).color })));
    if (colors[0].background !== 'rgb(39, 39, 42)' || colors[0].color !== 'rgb(243, 244, 246)') throw Error(JSON.stringify(colors));
    await page.screenshot({ path: '/tmp/hrms-dark-time-inputs.png' });
    const deskCss = fs.readFileSync(path.join(root, 'hrms/public/css/admin_reviews.css'), 'utf8');
    await page.setContent(`<html><head><style>body{margin:0;padding:16px}.frappe-control{max-width:500px;margin-bottom:12px}input{box-sizing:border-box;width:100%}${deskCss}</style></head><body><div class="admin-history-filters"><div class="form-section"><div class="section-body"><div class="form-column col-sm-12"><form>${['From Date','To Date','Project','Employee','Activity Type','Week Status','Group By'].map(label=>`<div class="frappe-control input-max-width"><label>${label}<input></label></div>`).join('')}</form></div></div></div></div></body></html>`);
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 844 });
      const layout = await page.locator('.frappe-control').evaluateAll(els => els.map(el => ({ x: el.getBoundingClientRect().x, y: el.getBoundingClientRect().y })));
      if (width === 1280 && layout[0].y !== layout[1].y) throw Error('Desktop history filters must share a row');
      if (width === 390 && layout[0].y === layout[1].y) throw Error('Mobile history filters must stack');
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw Error(`History filters overflow at ${width}`);
    }
    console.log('VISUAL_QA_OK', JSON.stringify({ viewports: [1280, 390], themes: ['light', 'dark'], nativeTimeColors: colors }));
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
