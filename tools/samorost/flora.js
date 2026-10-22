const fs=require('fs');
let seed=12345; const R=()=>{seed=(seed*16807)%2147483647;return (seed-1)/2147483646;};
const rr=(a,b)=>a+(b-a)*R(); const pick=a=>a[Math.floor(R()*a.length)];
const f=n=>{const v=Math.round(n*10)/10;return String(v);};
// ground
const segs=[[[380,610],[470,560],[600,545],[720,548]],[[720,548],[850,550],[980,555],[1080,570]],[[1080,570],[1150,580],[1200,595],[1230,615]]];
const pts=[];for(const s of segs)for(let t=0;t<=1;t+=0.002){const u=1-t;pts.push([0,1].map(i=>u*u*u*s[0][i]+3*u*u*t*s[1][i]+3*u*t*t*s[2][i]+t*t*t*s[3][i]));}
const gy=x=>{let best=pts[0];for(const p of pts)if(Math.abs(p[0]-x)<Math.abs(best[0]-x))best=p;return best[1];};
const blocked=(x,y)=>(x>752&&x<808&&y>460&&y<546)||(x>510&&x<572&&y>465&&y<556);
const out=[];const back=[];const front=[];
const greens=['#5d6b2e','#6f7a35','#4a5a2a','#7f8a3e','#3e4d26','#8a8a45','#566a3a','#9a9450'];
const earth=['#7a5a2e','#8c6a34','#5e4626'];
// ---------- mushroom
function mushroom(L,x,h,cw,ch,cap,opt={}){
  const by=gy(x)+(opt.dy||2); const lean=opt.lean||0; const tx=x+lean, ty=by-h;
  const sw=opt.sw||Math.max(2,cw*0.09);
  let s=`<ellipse cx="${f(x)}" cy="${f(by)}" rx="${f(sw*4)}" ry="${f(sw*1.2)}" fill="#1e1a0e" opacity="0.35"/>`;
  // stem: tapered curved
  const mx=x+lean*0.4+rr(-3,3);
  s+=`<path d="M${f(x-sw*1.3)},${f(by)} Q${f(mx-sw)},${f(by-h*0.5)} ${f(tx-sw*0.7)},${f(ty+ch*0.3)} L${f(tx+sw*0.7)},${f(ty+ch*0.3)} Q${f(mx+sw)},${f(by-h*0.5)} ${f(x+sw*1.3)},${f(by)} Z" fill="url(#flora-stem)" stroke="#3b2e1e" stroke-opacity="0.5" stroke-width="0.8" filter="url(#flora-rough)"/>`;
  // stem texture lines
  for(let i=0;i<3;i++){const o=rr(-sw*0.6,sw*0.6);s+=`<path d="M${f(x+o)},${f(by-2)} Q${f(mx+o)},${f(by-h*0.5)} ${f(tx+o*0.6)},${f(ty+ch*0.4)}" stroke="#4b3a24" stroke-opacity="${f(rr(.15,.35))}" stroke-width="0.6" fill="none"/>`;}
  s+=`<path d="M${f(x-sw*1.3)},${f(by)} Q${f(mx-sw)},${f(by-h*0.5)} ${f(tx-sw*0.7)},${f(ty+ch*0.3)} L${f(tx+sw*0.7)},${f(ty+ch*0.3)} Q${f(mx+sw)},${f(by-h*0.5)} ${f(x+sw*1.3)},${f(by)} Z" fill="#000" filter="url(#flora-grain)" opacity="0.5"/>`;
  // ring
  if(opt.ring){const ry=by-h*0.7;s+=`<path d="M${f(x+lean*0.6-sw*2)},${f(ry)} Q${f(x+lean*0.6)},${f(ry+5)} ${f(x+lean*0.6+sw*2)},${f(ry)}" stroke="#e8dcc0" stroke-width="2" fill="none" opacity="0.7"/>`;}
  // cap
  const shape=opt.shape||'dome';
  let capD;
  if(shape==='dome') capD=`M${f(tx-cw/2)},${f(ty+ch*0.35)} C${f(tx-cw/2)},${f(ty-ch*0.9)} ${f(tx+cw/2)},${f(ty-ch*0.9)} ${f(tx+cw/2)},${f(ty+ch*0.35)} Q${f(tx)},${f(ty+ch*0.12)} ${f(tx-cw/2)},${f(ty+ch*0.35)} Z`;
  else if(shape==='cone'){
    // bell / liberty cap: bulging sides, a small nipple on top, a wavy rim
    const tipx=tx+rr(-2,2)+lean*0.08, yb=ty+ch*0.4, yt=ty-ch*1.1;
    let d=`M${f(tx-cw/2)},${f(yb)} C${f(tx-cw*0.56)},${f(ty-ch*0.2)} ${f(tipx-cw*0.3)},${f(yt+ch*0.2)} ${f(tipx-cw*0.06)},${f(yt+ch*0.04)}`;
    d+=` Q${f(tipx)},${f(yt-ch*0.07)} ${f(tipx+cw*0.06)},${f(yt+ch*0.04)}`;
    d+=` C${f(tipx+cw*0.3)},${f(yt+ch*0.2)} ${f(tx+cw*0.56)},${f(ty-ch*0.2)} ${f(tx+cw/2)},${f(yb)}`;
    const sc=6;
    for(let i=1;i<=sc;i++){const u0=1-(i-1)/sc,u1=1-i/sc,um=(u0+u1)/2,yy=u=>yb-(1-(2*u-1)**2)*ch*0.22;
      d+=` Q${f(tx-cw/2+cw*um)},${f(yy(um)+ch*0.09)} ${f(tx-cw/2+cw*u1)},${f(yy(u1))}`;}
    capD=d+' Z';
  }
  else capD=`M${f(tx-cw/2)},${f(ty+ch*0.15)} C${f(tx-cw*0.4)},${f(ty-ch*0.55)} ${f(tx+cw*0.4)},${f(ty-ch*0.55)} ${f(tx+cw/2)},${f(ty+ch*0.15)} C${f(tx+cw*0.2)},${f(ty+ch*0.3)} ${f(tx-cw*0.2)},${f(ty+ch*0.3)} ${f(tx-cw/2)},${f(ty+ch*0.15)} Z`;
  // gills under cap
  if(opt.gills){let g='';const gyy=ty+ch*(shape==='flat'?0.2:0.35);for(let i=0;i<=14;i++){const gx=tx-cw*0.45+cw*0.9*i/14;g+=`M${f(tx)},${f(gyy-ch*0.05)} L${f(gx)},${f(gyy+ch*0.12)} `;}
    s+=`<ellipse cx="${f(tx)}" cy="${f(gyy+ch*0.05)}" rx="${f(cw*0.47)}" ry="${f(ch*0.14)}" fill="#c9b48a" opacity="0.9"/><path d="${g}" stroke="#6b5232" stroke-width="0.6" opacity="0.6"/>`;}
  s+=`<path d="${capD}" fill="url(#flora-cap-${cap})" stroke="#2e2116" stroke-opacity="0.55" stroke-width="1" filter="url(#flora-rough)"/>`;
  // cap texture: dab strokes
  s+=`<path d="${capD}" fill="url(#flora-shade)" opacity="0.5"/>`;
  s+=`<path d="${capD}" fill="#000" filter="url(#flora-grain)" opacity="0.6"/>`;
  if(shape==='cone'){
    const yb=ty+ch*0.4, yt=ty-ch*1.1;
    // gills peeking under the wavy rim
    s+=`<path d="M${f(tx-cw*0.44)},${f(yb-ch*0.02)} Q${f(tx)},${f(yb-ch*0.16)} ${f(tx+cw*0.44)},${f(yb-ch*0.02)} Q${f(tx)},${f(yb-ch*0.3)} ${f(tx-cw*0.44)},${f(yb-ch*0.02)} Z" fill="#6b5232" opacity="0.55"/>`;
    // radial striations from the tip down to the rim
    let st='';for(let i=1;i<10;i++){const u=i/10,bx=tx-cw*0.46+cw*0.92*u,by2=yb-(1-(2*u-1)**2)*ch*0.22-ch*0.04;
      st+=`M${f(tx+(u-0.5)*cw*0.12)},${f(yt+ch*0.22)} Q${f(tx+(u-0.5)*cw*0.75)},${f(ty-ch*0.25)} ${f(bx)},${f(by2)} `;}
    s+=`<path d="${st}" stroke="#4a3620" stroke-width="0.55" fill="none" opacity="0.35"/>`;
    // dark rim edge and a highlight following the bulge of the left side
    s+=`<path d="M${f(tx-cw/2)},${f(yb)} Q${f(tx)},${f(yb-ch*0.26)} ${f(tx+cw/2)},${f(yb)}" stroke="#2a1a0c" stroke-width="1.1" fill="none" opacity="0.35"/>`;
    s+=`<path d="M${f(tx-cw*0.36)},${f(yb-ch*0.3)} C${f(tx-cw*0.4)},${f(ty-ch*0.3)} ${f(tx-cw*0.2)},${f(yt+ch*0.3)} ${f(tx-cw*0.05)},${f(yt+ch*0.12)}" stroke="#fff3d6" stroke-opacity="0.4" stroke-width="${f(Math.max(1,cw*0.07))}" fill="none" stroke-linecap="round"/>`;
  } else {
  s+=`<path d="M${f(tx-cw/2)},${f(ty+ch*(shape==='flat'?0.15:0.35))} Q${f(tx)},${f(ty+ch*0.1)} ${f(tx+cw/2)},${f(ty+ch*(shape==='flat'?0.15:0.35))}" stroke="#2a1a0c" stroke-width="1.4" fill="none" opacity="0.5"/>`;
  // highlight
  s+=`<path d="M${f(tx-cw*0.3)},${f(ty-ch*0.15)} Q${f(tx-cw*0.1)},${f(ty-ch*0.55)} ${f(tx+cw*0.15)},${f(ty-ch*0.45)}" stroke="#fff3d6" stroke-opacity="0.35" stroke-width="${f(Math.max(1,ch*0.12))}" fill="none" stroke-linecap="round"/>`;
  }
  if(opt.spots){const n=opt.spots;for(let i=0;i<n;i++){const a=rr(-0.85,0.85),rad=rr(0.2,1);const sx=tx+a*cw*0.42, sy=ty-ch*0.25*rad-ch*0.3*(1-Math.abs(a))+ch*0.2;const r=rr(0.8,cw*0.06+1);s+=`<ellipse cx="${f(sx)}" cy="${f(sy)}" rx="${f(r)}" ry="${f(r*0.75)}" fill="${pick(['#efe6cf','#e6d9b5','#f5eedb'])}" opacity="${f(rr(.6,.95))}"/>`;}}
  (L||out).push(`<g>${s}</g>`);
}
// ---------- grass blade
function blade(x,y,h,col,w,lean){const tx=x+lean,ty=y-h;return `<path d="M${f(x-w)},${f(y)} Q${f(x+lean*0.3)},${f(y-h*0.6)} ${f(tx)},${f(ty)} Q${f(x+lean*0.3+w*0.5)},${f(y-h*0.55)} ${f(x+w)},${f(y)} Z" fill="${col}" opacity="${f(rr(.55,.95))}"/>`;}
// ---------- moss tuft
function moss(x,y,r){let s='';for(let i=0;i<10;i++){const a=rr(Math.PI,2*Math.PI),d=rr(0,r);s+=`<ellipse cx="${f(x+Math.cos(a)*d*1.6)}" cy="${f(y+Math.sin(a)*d*0.7+1)}" rx="${f(rr(1.5,r*0.6))}" ry="${f(rr(1,r*0.4))}" fill="${pick(greens)}" opacity="${f(rr(.35,.8))}"/>`;}
  for(let i=0;i<6;i++){s+=`<circle cx="${f(x+rr(-r*1.4,r*1.4))}" cy="${f(y-rr(0,r*0.6))}" r="${f(rr(.5,1.3))}" fill="${pick(['#b8b060','#c9c27a','#a4a752'])}" opacity="0.7"/>`;}
  return s;}
// ---------- fern
function fern(x,h,lean,col){const y=gy(x)+2;let s='';const tx=x+lean,ty=y-h;
  s+=`<path d="M${f(x)},${f(y)} Q${f(x+lean*0.2)},${f(y-h*0.6)} ${f(tx)},${f(ty)}" stroke="${col}" stroke-width="1.6" fill="none"/>`;
  // curl at tip
  let c=`M${f(tx)},${f(ty)}`;const dir=lean>=0?1:-1;for(let i=1;i<=14;i++){const a=i*0.5,r=7*(1-i/16);c+=` L${f(tx+dir*(Math.cos(a)*r-r*0.3)+dir*4)},${f(ty-Math.sin(a)*r)}`;}
  s+=`<path d="${c}" stroke="${col}" stroke-width="1.4" fill="none" stroke-linecap="round"/>`;
  for(let i=1;i<10;i++){const t=i/10;const px=x+(tx-x)*t+lean*0.2*Math.sin(t*Math.PI)*0.5,py=y-h*t;const len=(1-t)*h*0.35+3;
    for(const sd of [-1,1]){s+=`<path d="M${f(px)},${f(py)} Q${f(px+sd*len*0.6)},${f(py-len*0.5)} ${f(px+sd*len)},${f(py-len*0.15)}" stroke="${col}" stroke-width="${f(2.2*(1-t)+0.8)}" fill="none" opacity="0.85" stroke-linecap="round"/>`;}}
  return `<g filter="url(#flora-rough)">${s}</g>`;}
// ---------- puffball / dandelion
function puff(x,h,r){const y=gy(x)+2,tx=x+rr(-6,6),ty=y-h;let s=`<path d="M${f(x)},${f(y)} Q${f(x+rr(-5,5))},${f(y-h/2)} ${f(tx)},${f(ty)}" stroke="#8a8460" stroke-width="1" fill="none"/>`;
  s+=`<circle cx="${f(tx)}" cy="${f(ty)}" r="${f(r)}" fill="url(#flora-puff)"/>`;
  for(let i=0;i<22;i++){const a=R()*Math.PI*2,l=r*rr(.7,1);s+=`<line x1="${f(tx)}" y1="${f(ty)}" x2="${f(tx+Math.cos(a)*l)}" y2="${f(ty+Math.sin(a)*l)}" stroke="#f1ead6" stroke-width="0.35" opacity="0.6"/><circle cx="${f(tx+Math.cos(a)*l)}" cy="${f(ty+Math.sin(a)*l)}" r="0.7" fill="#f6f0e0" opacity="0.7"/>`;}
  s+=`<circle cx="${f(tx)}" cy="${f(ty)}" r="1.4" fill="#7a6a40"/>`;return s;}
// ---------- bulb plant
function bulb(x,h,col){const y=gy(x)+2;let s='';let cx=x,cy=y;const n=Math.floor(rr(2,4));
  const tx=x+rr(-10,10),ty=y-h;
  s+=`<path d="M${f(x-2)},${f(y)} Q${f(x+rr(-8,8))},${f(y-h*0.5)} ${f(tx)},${f(ty)}" stroke="#5b5a30" stroke-width="2.4" fill="none"/>`;
  for(let i=0;i<n;i++){const t=0.35+i*0.25;const bx=x+(tx-x)*t+rr(-2,2),by=y-h*t;const r=rr(3,6)*(1-t*0.4);s+=`<ellipse cx="${f(bx)}" cy="${f(by)}" rx="${f(r)}" ry="${f(r*1.2)}" fill="url(#flora-bulb-${col})" opacity="0.92"/>`;}
  const r=rr(7,11);s+=`<ellipse cx="${f(tx)}" cy="${f(ty-r*0.6)}" rx="${f(r)}" ry="${f(r*1.25)}" fill="url(#flora-bulb-${col})" stroke="#3b2e1e" stroke-opacity="0.4"/>`;
  s+=`<path d="M${f(tx-r*0.4)},${f(ty-r*1.6)} q${f(r*0.4)},${f(-6)} ${f(r*0.2)},${f(-12)}" stroke="#7a6a3a" stroke-width="1" fill="none"/><circle cx="${f(tx-r*0.2)}" cy="${f(ty-r*1.6-12)}" r="1.8" fill="#e8c86a"/>`;
  for(let i=0;i<5;i++)s+=`<circle cx="${f(tx+rr(-r*.6,r*.6))}" cy="${f(ty-r*0.6+rr(-r,r))}" r="${f(rr(.6,1.5))}" fill="#2e2a18" opacity="0.4"/>`;
  s+=`<ellipse cx="${f(tx-r*0.35)}" cy="${f(ty-r*1.0)}" rx="${f(r*0.25)}" ry="${f(r*0.4)}" fill="#fff6d8" opacity="0.3"/>`;
  return `<g filter="url(#flora-rough)">${s}</g>`;}
// ---------- flower
function flower(x,h,col){const y=gy(x)+2,tx=x+rr(-6,6),ty=y-h;let s=`<path d="M${f(x)},${f(y)} Q${f(x+rr(-4,4))},${f(y-h/2)} ${f(tx)},${f(ty)}" stroke="#56602e" stroke-width="1.1" fill="none"/>`;
  s+=`<path d="M${f(x+(tx-x)*0.4)},${f(y-h*0.4)} q6,-2 9,-7 q-6,0 -9,7" fill="#6a7a35" opacity="0.8"/>`;
  const n=5+Math.floor(R()*3);for(let i=0;i<n;i++){const a=i/n*Math.PI*2+R()*0.3;s+=`<ellipse cx="${f(tx+Math.cos(a)*3.5)}" cy="${f(ty+Math.sin(a)*2.6)}" rx="3" ry="1.6" transform="rotate(${f(a*180/Math.PI)} ${f(tx+Math.cos(a)*3.5)} ${f(ty+Math.sin(a)*2.6)})" fill="${col}" opacity="0.85"/>`;}
  s+=`<circle cx="${f(tx)}" cy="${f(ty)}" r="1.8" fill="#5a3a1e"/><circle cx="${f(tx-0.5)}" cy="${f(ty-0.5)}" r="0.7" fill="#f3d27a"/>`;return s;}
// ---------- glow mushroom
function glowShroom(x,h,cw){const y=gy(x)+2,tx=x+rr(-3,3),ty=y-h;let s='';
  s+=`<ellipse cx="${f(tx)}" cy="${f(ty)}" rx="${f(cw*1.8)}" ry="${f(cw*1.5)}" fill="url(#flora-glow)" />`;
  s+=`<path d="M${f(x)},${f(y)} Q${f(x+rr(-3,3))},${f(y-h/2)} ${f(tx)},${f(ty)}" stroke="#cfe6c4" stroke-width="${f(cw*0.18)}" fill="none" opacity="0.85"/>`;
  s+=`<path d="M${f(tx-cw/2)},${f(ty+1)} Q${f(tx)},${f(ty-cw*0.9)} ${f(tx+cw/2)},${f(ty+1)} Q${f(tx)},${f(ty-1)} ${f(tx-cw/2)},${f(ty+1)}Z" fill="#d9f5c8"/>`;
  s+=`<ellipse cx="${f(tx)}" cy="${f(ty-cw*0.15)}" rx="${f(cw*0.25)}" ry="${f(cw*0.12)}" fill="#ffffff" opacity="0.8"/>`;return s;}

// ===== moss carpet band =====
const gpath='M380,610 C470,560 600,545 720,548 C850,550 980,555 1080,570 C1150,580 1200,595 1230,615';
back.push(`<g filter="url(#flora-moss)"><path d="${gpath}" transform="translate(0,6)" stroke="#3e4a22" stroke-width="16" fill="none" opacity="0.55" stroke-linecap="round"/><path d="${gpath}" transform="translate(0,3)" stroke="#6f7a35" stroke-width="8" fill="none" opacity="0.6" stroke-linecap="round"/><path d="${gpath}" transform="translate(0,1)" stroke="#a4a752" stroke-width="3" fill="none" opacity="0.45" stroke-dasharray="6 9 3 12" stroke-linecap="round"/></g>`);
// ===== BACK GRASS/MOSS along ground =====
let g1='';
for(let x=385;x<=1228;x+=rr(2,4.5)){const y=gy(x)+rr(1,4);const h=rr(4,16)*((x<420||x>1190)?0.8:1);if(blocked(x,y-h))continue;
  g1+=blade(x,y,h,pick(greens),rr(.7,1.6),rr(-6,6));}
for(let x=385;x<=1228;x+=rr(7,13)){const y=gy(x)+3;if(blocked(x,y-6))continue;g1+=moss(x,y,rr(3,8));}
back.push(`<g filter="url(#flora-rough)">${g1}</g>`);

// ===== BIG MUSHROOM CLUSTER 660-720 =====
const cl=[]; // back to front
[[690,128,22,18,'bone','cone',{lean:-18}],[668,118,40,22,'rust','dome',{spots:9,lean:-10,ring:true}],
 [700,150,48,26,'ochre','dome',{spots:12,lean:4,gills:true,ring:true}],
 [722,95,30,26,'bone','cone',{lean:10}],
 [684,78,34,14,'bone','flat',{gills:true,lean:-4}],
 [660,62,26,16,'ochre','dome',{spots:5,lean:-12}],
 [712,58,24,12,'rust','flat',{gills:true,lean:6,spots:3}],
 [694,40,18,11,'bone','dome',{spots:3,lean:-3}],
 [735,34,14,10,'rust','dome',{lean:8,spots:2}],
 [672,28,13,8,'ochre','dome',{lean:-6}],
 [652,44,16,10,'bone','dome',{lean:-14,spots:2}],[706,24,11,7,'ochre','dome',{lean:2}],[726,18,9,6,'bone','dome',{}],[686,16,8,5,'rust','dome',{}],[744,22,10,7,'ochre','cone',{lean:4}],
].forEach(([x,h,cw,ch,c,sh,o])=>mushroom(cl,x,h,cw,ch,c,Object.assign({shape:sh},o)));
out.push(...cl);
// moss at base of cluster
let mb='';for(let x=650;x<745;x+=4)mb+=moss(x,gy(x)+3,rr(4,9));
for(let x=652;x<745;x+=2){const y=gy(x)+3;mb+=blade(x,y,rr(5,14),pick(greens),1,rr(-5,5));}
out.push(`<g filter="url(#flora-rough)">${mb}</g>`);

// ===== small groups 850-950 =====
const g2=[];
[[862,52,26,14,'rust','dome',{spots:6,lean:-5}],[876,36,18,10,'bone','dome',{spots:2,lean:3}],[852,24,12,8,'ochre','dome',{}],
 [925,70,30,12,'ochre','flat',{gills:true,lean:6}],[940,44,20,16,'bone','cone',{lean:-4}],[912,30,15,9,'rust','dome',{spots:3}],[952,20,10,7,'ochre','dome',{}]]
 .forEach(([x,h,cw,ch,c,sh,o])=>mushroom(g2,x,h,cw,ch,c,Object.assign({shape:sh},o)));
out.push(...g2);
// edge mushrooms
const g3=[];
[[405,40,20,11,'ochre','dome',{spots:4,lean:-6}],[420,26,14,8,'rust','dome',{lean:3}],[438,18,10,8,'bone','cone',{}],
 [1175,46,22,12,'rust','dome',{spots:5,lean:6}],[1192,30,14,9,'bone','dome',{spots:2,lean:-3}],[1160,22,12,9,'ochre','cone',{lean:4}],
 [1040,26,14,8,'bone','flat',{gills:true}],[1052,16,9,6,'rust','dome',{}], [620,24,12,8,'rust','dome',{spots:2}],[632,15,9,6,'ochre','dome',{}]]
 .forEach(([x,h,cw,ch,c,sh,o])=>mushroom(g3,x,h,cw,ch,c,Object.assign({shape:sh},o)));
out.push(...g3);

// ===== ferns, bulbs, puffs, flowers =====
let p='';
[[646,60,-14,'#5b6a2e'],[745,48,10,'#6a7535'],[830,55,-8,'#56652c'],[968,62,12,'#5f6c30'],[1010,40,-6,'#6f7a3a'],[455,44,-10,'#5b6a2e'],[1125,50,8,'#56652c'],[1213,30,10,'#6a7535']]
 .forEach(a=>p+=fern(...a));
[[838,60,'teal'],[888,48,'plum'],[1065,72,'teal'],[600,40,'plum'],[1140,42,'plum'],[992,36,'teal']].forEach(a=>p+=bulb(...a));
[[818,58,7],[900,72,9],[1095,64,8],[470,50,7],[1205,40,6],[640,82,8]].forEach(a=>p+=puff(...a));
[[848,22,'#e3c9a0'],[958,26,'#c97a4a'],[1022,20,'#e3c9a0'],[1110,24,'#b8846a'],[590,22,'#d9b26a'],[445,20,'#c97a4a'],[985,18,'#e8dcc0'],[1150,20,'#d9b26a']].forEach(a=>p+=flower(...a));
out.push(p);
// glow shrooms
let gl='';[[742,12,7],[748,9,5],[826,10,6],[895,9,5],[1075,11,6],[1083,8,4],[430,10,6],[1185,9,5],[598,9,5]].forEach(a=>gl+=glowShroom(...a));
out.push(`<g>${gl}</g>`);

// ===== front grass layer =====
let g4='';
for(let x=385;x<=1228;x+=rr(3,8)){const y=gy(x)+rr(4,8);const h=rr(3,10);if(blocked(x,y-h))continue;g4+=blade(x,y,h,pick(['#7f8a3e','#9a9450','#6f7a35','#a8a25a']),rr(.5,1.1),rr(-4,4));}
front.push(`<g filter="url(#flora-rough)">${g4}</g>`);

// ===== hanging vines =====
function vine(x0,y0,len,sway){let d=`M${f(x0)},${f(y0)}`;let s='';const steps=12;let px=x0,py=y0;const ph=R()*6;
  const ptsv=[];for(let i=1;i<=steps;i++){const t=i/steps;const x=x0+Math.sin(t*3+ph)*sway*t+sway*0.3*t;const y=y0+len*t;ptsv.push([x,y]);}
  for(const [x,y] of ptsv){d+=` L${f(x)},${f(y)}`;}
  s+=`<path d="${d}" stroke="#3e4a22" stroke-width="${f(rr(1.6,3))}" fill="none" stroke-linejoin="round" opacity="0.9"/>`;
  ptsv.forEach(([x,y],i)=>{if(R()<0.75){const sd=R()<0.5?-1:1;const l=rr(6,12);s+=`<path d="M${f(x)},${f(y)} q${f(sd*l)},${f(-l*0.2)} ${f(sd*l*1.2)},${f(l*0.6)} q${f(-sd*l*0.7)},${f(-l*0.1)} ${f(-sd*l*1.2)},${f(-l*0.6)}Z" fill="${pick(greens)}" opacity="${f(rr(.6,.95))}"/>`;}});
  const [ex,ey]=ptsv[ptsv.length-1];if(R()<0.5)s+=`<circle cx="${f(ex)}" cy="${f(ey+3)}" r="${f(rr(2,3.5))}" fill="${pick(['#c97a4a','#e3c9a0','#b0503a'])}" opacity="0.85"/>`;
  return s;}
function strand(x0,y0,len){let s='';const n=Math.floor(len/4);let x=x0;for(let i=0;i<n;i++){const y=y0+i*4;x+=rr(-1.2,1.2);s+=`<ellipse cx="${f(x)}" cy="${f(y)}" rx="${f(rr(1,2.6)*(1-i/n*0.6))}" ry="${f(rr(1.5,3))}" fill="${pick(['#7f8a3e','#9a9450','#8a8a45','#6f7a35'])}" opacity="${f(rr(.3,.7))}"/>`;}
  s+=`<path d="M${f(x0)},${f(y0)} L${f(x)},${f(y0+len)}" stroke="#6f7a35" stroke-width="0.6" opacity="0.5"/>`;return s;}
let v='';
// left edge — island surface at x 380-420 goes from y 610 down the side; attach slightly under ground line
for(let i=0;i<12;i++){const x=rr(378,425);const y=gy(x)+rr(4,14);v+=vine(x,y,rr(90,200),rr(-14,10));}
for(let i=0;i<10;i++){const x=rr(372,430);const y=gy(x)+rr(2,10);v+=strand(x,y,rr(40,130));}
for(let i=0;i<12;i++){const x=rr(1195,1242);const y=gy(Math.min(x,1230))+rr(4,14);v+=vine(x,y,rr(90,200),rr(-10,14));}
for(let i=0;i<10;i++){const x=rr(1190,1245);const y=gy(Math.min(x,1230))+rr(2,10);v+=strand(x,y,rr(40,130));}
// some moss clumps over edges
for(let x=372;x<432;x+=5)v+=moss(x,gy(x)+6,rr(4,8));
for(let x=1190;x<1240;x+=5)v+=moss(x,gy(Math.min(x,1230))+6,rr(4,8));
out.push(`<g filter="url(#flora-rough)">${v}</g>`);

// ===== lichen on house edges =====
function lichen(cx,cy,r){let s='';for(let i=0;i<16;i++){const a=R()*6.28,d=rr(0,r);s+=`<circle cx="${f(cx+Math.cos(a)*d)}" cy="${f(cy+Math.sin(a)*d)}" r="${f(rr(.8,r*0.35))}" fill="${pick(['#b9b47a','#a8a868','#cfc590','#c8a868','#8f9a5a'])}" opacity="${f(rr(.35,.75))}"/>`;}
  for(let i=0;i<5;i++){const a=R()*6.28,d=rr(r*.4,r);s+=`<circle cx="${f(cx+Math.cos(a)*d)}" cy="${f(cy+Math.sin(a)*d)}" r="${f(rr(1,2.2))}" fill="none" stroke="#e0d8a8" stroke-width="0.6" opacity="0.6"/>`;}return s;}
let lc='';[[446,520,8],[448,470,6],[452,430,7],[634,500,8],[630,450,6],[636,540,7],[470,395,6],[520,384,5],[600,392,7],[460,550,5],[624,555,5],[442,495,4]].forEach(a=>lc+=lichen(...a));
// a few tiny mushrooms on house left edge
out.push(`<g filter="url(#flora-rough)">${lc}</g>`);
mushroom(out,447,0,0,0,'ochre',{}); out.pop(); // keep RNG stable
// bracket fungi on house edges
let br='';[[444,505,14],[440,515,10],[637,470,13],[640,480,9]].forEach(([x,y,w])=>{const sd=x<540?-1:1;br+=`<path d="M${x},${y} q${sd*w},-4 ${sd*w},2 q${-sd*w*0.4},4 ${-sd*w},2Z" fill="url(#flora-cap-ochre)" stroke="#3b2e1e" stroke-opacity="0.5" stroke-width="0.7"/><path d="M${x},${y+1} q${sd*w*0.7},-2 ${sd*w*0.9},1" stroke="#efe6cf" stroke-width="0.7" fill="none" opacity="0.6"/>`;});
out.push(`<g filter="url(#flora-rough)">${br}</g>`);

const defs=`<defs>
<filter id="flora-rough" x="-20%" y="-20%" width="140%" height="140%"><feTurbulence type="fractalNoise" baseFrequency="0.06" numOctaves="2" seed="3" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.5" xChannelSelector="R" yChannelSelector="G"/></filter>
<filter id="flora-moss" x="-5%" y="-50%" width="110%" height="200%"><feTurbulence type="fractalNoise" baseFrequency="0.25" numOctaves="3" seed="11" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="9" xChannelSelector="R" yChannelSelector="G" result="d"/><feComposite in="d" in2="n" operator="in"/></filter>
<filter id="flora-grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="7" result="t"/><feColorMatrix in="t" type="matrix" values="0 0 0 0 0.15  0 0 0 0 0.1  0 0 0 0 0.05  0 0 0 1.6 -0.7" result="c"/><feComposite in="c" in2="SourceGraphic" operator="in"/></filter>
<radialGradient id="flora-cap-ochre" cx="40%" cy="30%" r="75%"><stop offset="0" stop-color="#e8b85e"/><stop offset="0.5" stop-color="#c08a3a"/><stop offset="1" stop-color="#6e4520"/></radialGradient>
<radialGradient id="flora-cap-rust" cx="40%" cy="30%" r="75%"><stop offset="0" stop-color="#d47a44"/><stop offset="0.55" stop-color="#a24a26"/><stop offset="1" stop-color="#5a2414"/></radialGradient>
<radialGradient id="flora-cap-bone" cx="40%" cy="30%" r="75%"><stop offset="0" stop-color="#f4ecd8"/><stop offset="0.55" stop-color="#d6c8a4"/><stop offset="1" stop-color="#8a7a5a"/></radialGradient>
<linearGradient id="flora-shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0.3" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#1e1408" stop-opacity="0.8"/></linearGradient>
<linearGradient id="flora-stem" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#6e5e40"/><stop offset="0.35" stop-color="#d4c7a6"/><stop offset="0.6" stop-color="#b8a882"/><stop offset="1" stop-color="#4e4028"/></linearGradient>
<radialGradient id="flora-puff"><stop offset="0" stop-color="#f4eedc" stop-opacity="0.5"/><stop offset="1" stop-color="#f4eedc" stop-opacity="0.05"/></radialGradient>
<radialGradient id="flora-glow"><stop offset="0" stop-color="#d4ffb0" stop-opacity="0.7"/><stop offset="0.4" stop-color="#9fe0a0" stop-opacity="0.25"/><stop offset="1" stop-color="#7fd0a0" stop-opacity="0"/></radialGradient>
<radialGradient id="flora-bulb-teal" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#a8c8a0"/><stop offset="0.6" stop-color="#4f7a68"/><stop offset="1" stop-color="#22382e"/></radialGradient>
<radialGradient id="flora-bulb-plum" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#d8a890"/><stop offset="0.6" stop-color="#8a4a48"/><stop offset="1" stop-color="#3a1e1e"/></radialGradient>
</defs>`;
const svg=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">
${defs}
<g id="layer-flora">
${back.join('\n')}
${out.join('\n')}
${front.join('\n')}
</g>
</svg>`;
fs.writeFileSync(process.argv[2]||require('path').join(__dirname,'../../art/samorost/layers/flora.svg'),svg);
console.log(svg.length);
