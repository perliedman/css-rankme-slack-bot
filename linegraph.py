from pygooglechart import SimpleLineChart

colors = ['7cb5ec', '434348', '90ed7d', 'f7a35c', '8085e9',
   'f15c80', 'e4d354', '2b908f', 'f45b5b', '91e8e1']

def get_chart_url(series):
    chart = SimpleLineChart(640, 400)

    chart.set_legend([name for (name, _) in series])
    chart.set_colours_within_series(colors[0:len(series)])

    for (_, data) in series:
        chart.add_data(data)


    return chart.get_url()

if __name__ == '__main__':
    print get_chart_url([
        ('perl', [1141, 1141, 1162, 1168, 1168, 1190, 1197, 1208, 1232, 1230, 1263, 1260, 1258, 1287, 1301, 1326, 1397, 1397, 1397, 1397, 1367, 1440, 1470, 1470, 1470, 1470, 1470, 1470, 1470, 1468, 1468, 1518,]),
        ('larchii', [1445, 1446, 1487, 1483, 1483, 1491, 1491, 1530, 1540, 1530, 1649, 1717, 1717, 1717, 1717, 1737, 1700, 1752, 1752, 1752, 1755, 1770, 1781, 1781, 1781, 1781, 1781, 1781, 1781, 1781, 1781, 1787,])
    ])
