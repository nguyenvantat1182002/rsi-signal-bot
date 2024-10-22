

v = []

for i in range(20):
    if not v:
        v.append(0.02)
    elif len(v) < 2:
        v.append(v[0] * 2)
    else:
        v.append(round(v[-2] + v[-1], 2))

print(v)

