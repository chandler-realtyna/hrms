const n="-05:00";function i(t,e){if(!e)return null;const r=String(e);return/([+-]\d{2}:?\d{2}|Z)$/.test(r)?t(r):t(r.replace(" ","T")+n)}function o(t,e){const r=i(t,e);return!r||!r.isValid()?"":r.fromNow()}export{o as t};
//# sourceMappingURL=serverTime-DBpoZb1N.js.map
