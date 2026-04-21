/* ── Shared Sidebar Component ───────────────────────────────
   Load with: <script type="text/babel" data-presets="react" src="sidebar.jsx"></script>
   Exports window.AppSidebar
   ─────────────────────────────────────────────────────────── */

(function() {

const NAV = [
  { group: "Overview", items: [
    { id:"overview",      label:"Dashboard",         sigil:"◎", href:"/",                  match:["index","Dashboard"] },
  ]},
  { group: "Keeper Tools", items: [
    { id:"characters",    label:"Investigators",     sigil:"✶", href:"/characters",        match:["characters","retired"] },
    { id:"grimoire",      label:"Grimoire",          sigil:"Ψ", href:"/grimoire",          match:["monsters","deities","spells","weapons","occupations","skills","manias","phobias","archetypes","pulp","insane","poisons","inventions","grimoire"] },
  ]},
  { group: "Audio", items: [
    { id:"soundboard",    label:"Soundboard",        sigil:"◐", href:"/admin/soundboard",  match:["soundboard","Soundboard"] },
    { id:"music",         label:"Music Bot",         sigil:"♪", href:"/admin/music",       match:["music","Music"] },
  ]},
  { group: "Server Admin", items: [
    { id:"karma",         label:"Karma",             sigil:"☥", href:"/admin/karma",       match:["karma"] },
    { id:"autoroom",      label:"Auto Rooms",        sigil:"⌘", href:"/admin/autorooms",   match:["autoroom"] },
    { id:"roles",         label:"Reaction Roles",    sigil:"✧", href:"/admin/reactionroles",match:["reactionroles"] },
    { id:"deleter",       label:"Auto Deleter",      sigil:"⌫", href:"/admin/deleter",     match:["deleter"] },
    { id:"polls",         label:"Polls & Reminders", sigil:"◈", href:"/admin/polls",       match:["polls","reminders"] },
    { id:"rss",           label:"RSS & Feeds",       sigil:"⌁", href:"/admin/rss",         match:["rss"] },
    { id:"giveaway",      label:"Giveaways",         sigil:"✦", href:"/admin/giveaway",    match:["giveaway"] },
    { id:"enroll",        label:"Enrollment",        sigil:"✎", href:"/admin/enroll",      match:["enroll"] },
  ]},
  { group: "System", items: [
    { id:"config",        label:"Bot Config",        sigil:"⚙", href:"/admin/bot_config",  match:["bot_config","config"] },
    { id:"backup",        label:"Backup",            sigil:"⧗", href:"/admin/backup",      match:["backup"] },
  ]},
];

/* Detect active item from current page title / pathname */
function detectActive() {
  const path = window.location.pathname + " " + document.title;
  for (const group of NAV) {
    for (const item of group.items) {
      if (item.match.some(m => path.toLowerCase().includes(m.toLowerCase()))) {
        return item.id;
      }
    }
  }
  return "overview";
}

/* Pentacle sigil */
const SidebarSigil = ({size=42}) => {
  const r=size*.41, cx=size/2, cy=size/2;
  const a = d => [cx+r*Math.cos(d*Math.PI/180), cy+r*Math.sin(d*Math.PI/180)];
  const [x0,y0]=a(-90),[x1,y1]=a(-18),[x2,y2]=a(54),[x3,y3]=a(126),[x4,y4]=a(198);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none" stroke="currentColor" strokeWidth="0.9">
      <circle cx={cx} cy={cy} r={size*.47} opacity=".4"/>
      <path d={`M${x0},${y0} L${x2},${y2} L${x4},${y4} L${x1},${y1} L${x3},${y3} Z`} strokeLinejoin="miter"/>
      <circle cx={cx} cy={cy} r={size*.035} fill="currentColor"/>
    </svg>
  );
};

function AppSidebar() {
  const storageKey = "cthulhu-sidebar-collapsed";
  const [collapsed, setCollapsed] = React.useState(() => {
    try { return localStorage.getItem(storageKey) === "1"; } catch { return false; }
  });
  const [active] = React.useState(detectActive);
  const [online, setOnline] = React.useState(true);

  const toggle = () => setCollapsed(c => {
    const next = !c;
    try { localStorage.setItem(storageKey, next ? "1" : "0"); } catch {}
    return next;
  });

  /* Poll bot status */
  React.useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/api/status', {cache:"no-store"});
        const data = await res.json();
        setOnline(data.status === "online");
      } catch { setOnline(false); }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  const W = collapsed ? 68 : 256;

  return (
    <aside style={{
      width: W, flexShrink: 0,
      background: "var(--void-1)",
      borderRight: "1px solid var(--hair)",
      display: "flex", flexDirection: "column",
      position: "sticky", top: 0, alignSelf: "flex-start",
      height: "100vh", overflow: "hidden",
      transition: "width .25s cubic-bezier(.4,0,.2,1)",
      zIndex: 50,
    }}>

      {/* Brand */}
      <a href="/" style={{
        padding: collapsed ? "20px 13px" : "22px 20px",
        borderBottom: "1px solid var(--hair)",
        display: "flex", alignItems: "center", gap: 12,
        textDecoration: "none", color: "inherit",
        flexShrink: 0,
      }}>
        <div style={{color:"var(--sigil)", flexShrink:0, animation:"breathe 5.5s ease-in-out infinite"}}>
          <SidebarSigil size={collapsed ? 38 : 42}/>
        </div>
        {!collapsed && (
          <div style={{overflow:"hidden"}}>
            <div style={{fontFamily:"'IM Fell English SC','IM Fell English',serif", fontSize:18, lineHeight:1, letterSpacing:"0.05em", whiteSpace:"nowrap"}}>CthulhuBot</div>
            <div style={{fontFamily:"'IBM Plex Mono',monospace", fontSize:8, letterSpacing:"0.26em", color:"var(--bone-fade)", marginTop:4, whiteSpace:"nowrap"}}>KEEPER · v2</div>
          </div>
        )}
      </a>

      {/* Nav */}
      <nav style={{flex:1, overflowY:"auto", overflowX:"hidden", padding: collapsed ? "12px 8px" : "16px 12px"}}>
        {NAV.map(group => (
          <div key={group.group} style={{marginBottom:20}}>
            {!collapsed && (
              <div style={{fontFamily:"'IBM Plex Mono',monospace", fontSize:10, letterSpacing:"0.22em", textTransform:"uppercase", color:"var(--bone-fade)", padding:"0 8px 7px"}}>
                {group.group}
              </div>
            )}
            {group.items.map(item => {
              const isActive = active === item.id;
              return (
                <a key={item.id} href={item.href} title={item.label}
                  style={{
                    display:"flex", alignItems:"center", gap:10,
                    padding: collapsed ? "9px 0" : "8px 10px",
                    justifyContent: collapsed ? "center" : "flex-start",
                    color: isActive ? "var(--sigil)" : "var(--bone-dim)",
                    background: isActive ? "rgba(120,220,170,0.06)" : "transparent",
                    borderLeft: isActive ? "2px solid var(--sigil)" : "2px solid transparent",
                    fontSize: 13, letterSpacing:"0.02em",
                    transition: "all .15s",
                    textDecoration: "none",
                  }}
                  onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = "var(--bone)"; }}
                  onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = "var(--bone-dim)"; }}
                >
                  <span style={{
                    fontFamily:"'IM Fell English SC','IM Fell English',serif",
                    fontSize:14, width:16, textAlign:"center", flexShrink:0,
                    color: isActive ? "var(--sigil)" : "var(--bone-fade)",
                  }}>{item.sigil}</span>
                  {!collapsed && <span style={{flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{item.label}</span>}
                </a>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div style={{padding: collapsed ? "12px 8px" : "14px 16px", borderTop:"1px solid var(--hair)", flexShrink:0}}>
        {!collapsed ? (
          <div>
            <div style={{display:"flex", alignItems:"center", gap:8, marginBottom:10}}>
              <span style={{
                width:7, height:7, borderRadius:"50%", flexShrink:0,
                background: online ? "var(--sigil)" : "var(--bone-fade)",
                boxShadow: online ? "0 0 8px var(--sigil-g)" : "none",
                animation: online ? "pulse-dot 2.2s ease-in-out infinite" : "none",
              }}/>
              <span style={{fontFamily:"'IBM Plex Mono',monospace", fontSize:9, letterSpacing:"0.18em", color: online ? "var(--bone-dim)" : "var(--bone-fade)"}}>
                {online ? "ONLINE" : "OFFLINE"}
              </span>
            </div>
            <button onClick={toggle}
              style={{fontFamily:"'IBM Plex Mono',monospace", fontSize:9, letterSpacing:"0.18em", color:"var(--bone-fade)", cursor:"pointer", background:"none", border:"none"}}>
              ⟨ COLLAPSE
            </button>
          </div>
        ) : (
          <div style={{display:"flex", flexDirection:"column", gap:8, alignItems:"center"}}>
            <span style={{
              width:7, height:7, borderRadius:"50%",
              background: online ? "var(--sigil)" : "var(--bone-fade)",
              boxShadow: online ? "0 0 8px var(--sigil-g)" : "none",
              animation: online ? "pulse-dot 2.2s ease-in-out infinite" : "none",
            }}/>
            <button onClick={toggle} style={{color:"var(--bone-fade)", cursor:"pointer", background:"none", border:"none", fontSize:14}}>⟩</button>
          </div>
        )}
      </div>
    </aside>
  );
}

window.AppSidebar = AppSidebar;

})();
