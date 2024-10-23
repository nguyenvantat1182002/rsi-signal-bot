

v = [0.02]

for i in range(20):
    v.append(round(v[0] * 2 if len(v) < 2 else v[-2] + v[-1], 2))

print(v)

