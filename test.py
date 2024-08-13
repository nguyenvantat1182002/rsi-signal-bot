

with open('a.txt', encoding='utf-8') as file:
    lines_a = file.read().splitlines()

with open('b.txt', encoding='utf-8') as file:
    lines_b = file.read().splitlines()
    lines_b = [item for item in lines_b if len(item) > 0]

target = ''

output = [item for item in lines_a if target in item]

for item_a in output:
    items = item_a.split('|')
    username = item_a[0]

    result = [item for item in lines_b if item.startswith(username)]
    if result:
        with open('out.txt', 'a', encoding='utf-8') as file:
            file.write(f'{result[0]}\n')



