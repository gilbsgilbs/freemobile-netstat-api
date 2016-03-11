// Load the Visualization API.
google.load('visualization', '1', {
    'packages' : [ 'corechart' ]
});
var CHART_OPTIONS = {
    width : 800,
    height : 350,
    pieSliceText: 'none',
    legend: 'labeled',
    chartArea : {
        left : (940 - 550) / 2,
        top : 15,
        width : 550,
        height : "325"
    }
};

// Set a callback to run when the Google Visualization API is loaded.
google.setOnLoadCallback(initChart);
var sliderInitialized = false;

function getLimitDates() {
    var $dateRangePicker = $('#date-range-picker');
    var limitDates = $dateRangePicker.text().split(' -> ');
    var startDate = limitDates[0].split('/');
    var endDate = limitDates[1].split('/');
    return [startDate.reverse().join(''), endDate.reverse().join('')];
}

function initDateRangePicker() {
    var $dateRangePicker = $('#date-range-picker');
    var start = moment().subtract(6, 'days');
    var end = moment();

    $dateRangePicker.dateRangePicker({
            format: 'DD/MM/YYYY',
            startOfWeek: 'monday',
            separator: ' -> ',
            getValue: function() {
                return this.innerHTML;
            },
            setValue: function(s) {
                this.innerHTML = s;
            }
    })
    .bind('datepicker-change', function() {
        loadData();
    })
    .data('dateRangePicker').setDateRange(start.format('DD/MM/YYYY'), end.format('DD/MM/YYYY'));
}

function initChart() {
    initDateRangePicker();
    loadData();
}

function loadData() {
    var limitDates = getLimitDates();
    $.get('/2/chart/network-usage?start_date=' + limitDates[0] + '&end_date=' + limitDates[1] + '', drawCharts).error(dataLoadError);
}

function dataLoadError() {
    var networkUsageSpinner = $("#network-usage-spinner");
    networkUsageSpinner.empty();
    networkUsageSpinner.append("Données non disponibles pour le moment");
}

function drawCharts(jsonData) {
    var usersElement = $("#users");

    var stats_global = jsonData["stats_global"];
    var stats_4g = jsonData["stats_4g"];
    var users = stats_global["users"];
    var users4g = stats_4g["users"];

    usersElement.text(users);
    var limitDates = getLimitDates();
    var days = moment(limitDates[1], 'YYYYMMDD').diff(moment(limitDates[0], 'YYYYMMDD'), 'days') + 1;
    $("#days").text(days);

    var $chartsSlider = $('.charts-slider');
    $chartsSlider.show();
    drawNetworkUsageChart(stats_global["time_on_orange"], stats_global["time_on_free_mobile"],
                          stats_global["time_on_free_mobile_femtocell"]);
    draw4gNetworkUsageChart(stats_4g["time_on_orange"], stats_4g["time_on_free_mobile_3g"],
                            stats_4g["time_on_free_mobile_4g"], stats_4g["time_on_free_mobile_femtocell"]);

    $("#network-usage-spinner").remove();


    if (!sliderInitialized) {
        // A bit hacky, but it seems to be the only way to workaround the greedy Google Chart which paints over the
        // slider by default.
        $chartsSlider.slick({infinite: true});
        sliderInitialized = true;
    }

    $("#network-usage-chart").fadeIn(function() {
       $("#chart-help").slideDown();
    });
    $chartsSlider.on('beforeChange', function (event, slick, oldIndex, newIndex) {
        if (newIndex === 0) {
            usersElement.text(users);
        }
        else if (newIndex === 1) {
            usersElement.text(users4g);
        }
    });
}

function drawNetworkUsageChart(onOrange, onFreeMobile, onFreeMobileFemtocell) {
    var data = new google.visualization.DataTable();
    data.addColumn("string", "Réseau");
    data.addColumn("number", "Utilisation");

    data.addRows(3);
    data.setCell(0, 0, "Orange");
    data.setCell(0, 1, onOrange, "");
    data.setCell(1, 0, "Free Mobile");
    data.setCell(1, 1, onFreeMobile, "");
    data.setCell(2, 0, "Femtocell");
    data.setCell(2, 1, onFreeMobileFemtocell, "");

    var chart = new google.visualization.PieChart($("#network-usage-chart").get(0));
    var options = CHART_OPTIONS;
    options.colors = [ "#FF6600", "#CD1E25", "#D2343A" ];
    chart.draw(data, options);
}

function draw4gNetworkUsageChart(onOrange, onFreeMobile3g, onFreeMobile4g, onFreeMobileFemtocell) {
    var data = new google.visualization.DataTable();
    data.addColumn("string", "Type de réseau");
    data.addColumn("number", "Utilisation");

    data.addRows(4);
    data.setCell(0, 0, "Orange");
    data.setCell(0, 1, onOrange, "");
    data.setCell(1, 0, "Femtocell");
    data.setCell(1, 1, onFreeMobileFemtocell, "");
    data.setCell(2, 0, "3G Free Mobile");
    data.setCell(2, 1, onFreeMobile3g, "");
    data.setCell(3, 0, "4G Free Mobile");
    data.setCell(3, 1, onFreeMobile4g, "");

    var chart = new google.visualization.PieChart($("#network-4g-usage-chart").get(0));
    var options = CHART_OPTIONS;
    options.colors = [ "#FF6600", "#D2343A", "#CD1E25", "#660F12" ];
    chart.draw(data, options);
}
