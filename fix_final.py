import re

with open('/root/openclaw/kimi/downloads/19cc89d6-7a52-8a8b-8000-0000cdc27c10_DOCTYPE_html.txt', 'r') as f:
    content = f.read()

# 1. Fix CDN
content = content.replace(
    'cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js',
    'cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'
)

# 2. Fix const S to window.S
content = re.sub(r'\bconst\s+S\s*=\s*\{', 'window.S = {', content)

# 3. Fix TRADE_HIST to TRADES
content = content.replace('TRADE_HIST', 'TRADES')

# 4. Replace const/let with var
content = re.sub(r'\bconst\s+', 'var ', content)
content = re.sub(r'\blet\s+', 'var ', content)

# 5. Replace arrow functions - carefully
content = re.sub(r'\b(\w+)\s*=>\s*([^,{;]+?)(?=[,);]|$)', r'function(\1){return \2;}', content)
content = re.sub(r'\(([^)]+)\)\s*=>\s*([^,{;]+?)(?=[,);]|$)', r'function(\1){return \2;}', content)
content = re.sub(r'\b(\w+)\s*=>\s*\{', r'function(\1){', content)
content = re.sub(r'\(([^)]+)\)\s*=>\s*\{', r'function(\1){', content)

# 6. Fix ...CD 
lines = content.split('\n')
result = []
for line in lines:
    if '{...CD,plugins:{legend:{display:false}}}}' in line:
        line = line.replace('{...CD,plugins:{legend:{display:false}}}}', '''{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}},y:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}}}}''')
    elif 'options:{...CD}}' in line:
        line = line.replace('options:{...CD}}', '''options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8899aa',font:{size:11}}},tooltip:{backgroundColor:'#1a2636',titleColor:'#e0eaf5',bodyColor:'#c0d0e0'}},scales:{x:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}},y:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}}}}''')
    elif 'options:{...CD,' in line:
        line = line.replace('options:{...CD,', '''options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8899aa',font:{size:11}}},tooltip:{backgroundColor:'#1a2636',titleColor:'#e0eaf5',bodyColor:'#c0d0e0'}},scales:{x:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}},y:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}},''')
    elif '...CD.plugins' in line:
        line = line.replace('...CD.plugins', "{legend:{labels:{color:'#8899aa',font:{size:11}}},tooltip:{backgroundColor:'#1a2636',titleColor:'#e0eaf5',bodyColor:'#c0d0e0'}}")
    elif '...CD.scales.x' in line:
        line = line.replace('...CD.scales.x', "{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}")
    elif '...CD.scales.y' in line:
        line = line.replace('...CD.scales.y', "{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}")
    elif '...CD.scales' in line:
        line = line.replace('...CD.scales', "{x:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}},y:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}}")
    elif '...CD' in line:
        line = line.replace('...CD', "{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8899aa',font:{size:11}}},tooltip:{backgroundColor:'#1a2636',titleColor:'#e0eaf5',bodyColor:'#c0d0e0'}},scales:{x:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}},y:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}}}")
    result.append(line)

content = '\n'.join(result)

with open('/root/.openclaw/workspace/index_final_v2.html', 'w') as f:
    f.write(content)

print('Fixes applied')
