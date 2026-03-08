import re

with open('/tmp/cd_fix.html', 'r') as f:
    content = f.read()

# CD object definition
cd_obj = "{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8899aa',font:{size:11}}},tooltip:{backgroundColor:'#1a2636',titleColor:'#e0eaf5',bodyColor:'#c0d0e0'}},scales:{x:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}},y:{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}}}"

# Replace ...CD in various contexts
content = content.replace('options:{...CD,plugins:', 'options:{' + cd_obj.replace('}}}', ',plugins:'))
content = content.replace('options:{...CD}}', 'options:' + cd_obj + '}')
content = content.replace('options:{...CD}', 'options:' + cd_obj)

# Replace ...CD.plugins
content = content.replace('...CD.plugins', "{legend:{labels:{color:'#8899aa',font:{size:11}}},tooltip:{backgroundColor:'#1a2636',titleColor:'#e0eaf5',bodyColor:'#c0d0e0'}}")

# Replace ...CD.scales.x
content = content.replace('...CD.scales.x', "{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}")

# Replace ...CD.scales.y
content = content.replace('...CD.scales.y', "{ticks:{color:'#5a7080',font:{size:10}},grid:{color:'rgba(255,255,255,.04)'}}")

# Replace remaining ...CD
content = content.replace('...CD', cd_obj)

with open('/tmp/cd_fixed.html', 'w') as f:
    f.write(content)

print('CD spread operator fixes applied')
