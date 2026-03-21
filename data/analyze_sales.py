import csv
from collections import defaultdict
from datetime import datetime

rows = []
with open(r'c:\Users\mrcra\Desktop\mini-claude\data\sales.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        row['quantity'] = int(row['quantity'])
        row['unit_price'] = float(row['unit_price'])
        row['total'] = float(row['total'])
        row['date'] = datetime.strptime(row['date'], '%Y-%m-%d')
        rows.append(row)

total_revenue = sum(r['total'] for r in rows)
total_orders = len(rows)
total_units = sum(r['quantity'] for r in rows)
avg_order = total_revenue / total_orders

by_month = defaultdict(float)
by_month_orders = defaultdict(int)
for r in rows:
    key = r['date'].strftime('%Y-%m')
    by_month[key] += r['total']
    by_month_orders[key] += 1

by_sp = defaultdict(float)
by_sp_orders = defaultdict(int)
by_sp_units = defaultdict(int)
for r in rows:
    by_sp[r['salesperson']] += r['total']
    by_sp_orders[r['salesperson']] += 1
    by_sp_units[r['salesperson']] += r['quantity']

by_reg = defaultdict(float)
for r in rows:
    by_reg[r['region']] += r['total']

by_cat = defaultdict(float)
by_cat_units = defaultdict(int)
for r in rows:
    by_cat[r['category']] += r['total']
    by_cat_units[r['category']] += r['quantity']

by_prod = defaultdict(float)
by_prod_units = defaultdict(int)
for r in rows:
    by_prod[r['product']] += r['total']
    by_prod_units[r['product']] += r['quantity']

months = sorted(by_month.keys())
mom = []
for i in range(1, len(months)):
    prev = by_month[months[i-1]]
    curr = by_month[months[i]]
    growth = ((curr - prev) / prev) * 100
    mom.append((months[i-1], months[i], growth))

best = max(rows, key=lambda x: x['total'])
worst = min(rows, key=lambda x: x['total'])

print(total_revenue, total_orders, total_units, round(avg_order,2))
for m in sorted(by_month): print('MONTH', m, round(by_month[m],2), by_month_orders[m])
for sp, rev in sorted(by_sp.items(), key=lambda x: -x[1]): print('SP', sp, round(rev,2), by_sp_orders[sp], by_sp_units[sp])
for reg, rev in sorted(by_reg.items(), key=lambda x: -x[1]): print('REG', reg, round(rev,2))
for cat, rev in sorted(by_cat.items(), key=lambda x: -x[1]): print('CAT', cat, round(rev,2), by_cat_units[cat])
for prod, rev in sorted(by_prod.items(), key=lambda x: -x[1])[:5]: print('PROD', prod, round(rev,2), by_prod_units[prod])
for m1,m2,g in mom: print('MOM', m1, m2, round(g,1))
print('BEST', best['order_id'], best['salesperson'], best['product'], best['total'])
print('WORST', worst['order_id'], worst['salesperson'], worst['product'], worst['total'])
