//document.getElementById("lichange1").onclick = function() {changePage1()};
//document.getElementById("lichange2").onclick = function() {changePage2()};
//document.getElementById("demo").onclick = function() {myFunction()};

function hideShow() {
  var x = document.getElementById("WarningData");
  if (x.style.display === "none" || x.style.display === "") {
    x.style.display = "block";
  } else {
    x.style.display = "none";
  }
}



function changePage1() {

  if (document.getElementById("csvimportdataform").style.display != "none") {
    document.getElementById("csvimportdataform").style.display = "none";
    document.getElementsByClassName("SubmitData")[0].style.display = "block";
  }
}

function changePage2() {

  if (document.getElementById("csvimportdataform").style.display == "" || document.getElementById("csvimportdataform").style.display == "none") {
    document.getElementById("csvimportdataform").style.display = "block";
    document.getElementsByClassName("SubmitData")[0].style.display = "none";
  }
}

function changePage3() {  
  if (document.getElementById("AddFinancialInstrument").style.display != "none") {
    document.getElementById("AddFinancialInstrument").style.display = "none";
    document.getElementById("addcustomfields").innerHTML = "";
  }
}

function changePage4() {
  if (document.getElementById("AddFinancialInstrument").style.display == "none" || document.getElementById("AddFinancialInstrument").style.display == "" ) {
    document.getElementById("AddFinancialInstrument").style.display = "block";
  }

  if ( document.getElementById("csvimportdataform").style.display != "none" ) {
    document.getElementById("csvimportdataform").style.display = "none";
  }
  if ( document.getElementsByClassName("SubmitData")[0].style.display == "none" ) {
    document.getElementsByClassName("SubmitData")[0].style.display = "block";
  }
}

/*
  var submitDataa = document.getElementById("importdata").style.display;
  if ( submitDataa ==  "block" || submitDataa == "" ) {
    submitDataa = "none";
  }  
  var csvfileupload = document.getElementById("csvfile").style.display;
  if ( csvfileupload = "none" || csvfileupload == "" ) {
    csvfileupload = "block";
  }
  document.getElementById("addcustomfields").innerHTML = "";
}
*/

document.getElementById("lichange1").addEventListener("click", changePage3);
document.getElementById("lichange2").addEventListener("click", changePage3);
document.getElementById("lichange3").addEventListener("click", changePage4);

function handleFormmm(e) {
  document.getElementById("myFormSubmit").submit();
  e.preventDefault();
  //rest of the code
}

function warningResult1(data_) {
    if (Object.keys(data_).length > 0) {
      myheader = "<a href='https://interactivebrokers.github.io/tws-api/message_codes.html' target = '_blank'>Click here to know more about IB errors</a> <br>";
      mywarningTable = "<br>";
      mywarningTable += "<table id='responsive-data-table' class='table dt-responsive nowrap'>";
      mywarningTable += "<thead class='warningChangeColor'> <tr style='background-color: #F95959'> <th>Ticker</th> <th>Cusip</th> <th>Reason</th>";
      mywarningTable += "</tr> </thead>";
      mywarningTable += "<tbody>";
      for (let x in data_) {
        var mywarning = data_[x];
        mywarningTable += "<tr>";
        mywarningTable += "<td>" + mywarning[0] + "</td> <td>" + mywarning[1] + "</td> <td>" + mywarning[2] + "</td>";
        mywarningTable += "</tr>";
      }
      mywarningTable += "<t/body>";
      mywarningTable += "<t/table>";
      document.getElementById("WarningData").innerHTML = myheader + mywarningTable;
    }
  } 



/*******************************************************/
/**********On Change Table Input***************/

document.getElementById("ComparisonFastSMA").addEventListener("change", changeInput);
document.getElementById("ComparisonSlowSMA").addEventListener("change", changeInput);
document.getElementById("ComparisonVWAP").addEventListener("change", changeInput);
document.getElementById("ComparisonRSI").addEventListener("change", changeInput);
document.getElementById("ComparisonAverageVolume").addEventListener("change", changeInput);
document.getElementById("ComparisonVolume").addEventListener("change", changeInput);
document.getElementById("ComparisonRelativeVolume").addEventListener("change", changeInput);

document.getElementById("ComparisonEMA").addEventListener("change", changeInput);
document.getElementById("ComparisonOBV").addEventListener("change", changeInput);
document.getElementById("ComparisonATR").addEventListener("change", changeInput);

document.getElementById("ComparisonPrevClose").addEventListener("change", changeInput);
document.getElementById("ComparisonLowOfDay").addEventListener("change", changeInput);
document.getElementById("ComparisonHighOfDay").addEventListener("change", changeInput);
document.getElementById("ComparisonPullbackPct2").addEventListener("change", changeInput);
document.getElementById("ComparisonFibGap").addEventListener("change", changeInput);
document.getElementById("ComparisonMarketCap").addEventListener("change", changeInput);
//document.getElementById("ComparisonPrice").addEventListener("change", changeInput);

function changeInput() {
  var x = document.getElementById(this.id);
  x.value = x.value;
  if (x.value == "between") {

    if (this.id == "ComparisonFastSMA") {var id1 = "PercentageFastSMA"; var id2 = "PercentageFastSMA1"; var id3 = "changeinput1"; var val1 = 0; var val2 = 100;}
    if (this.id == "ComparisonSlowSMA") {var id1 = "PercentageSlowSMA"; var id2 = "PercentageSlowSMA1"; var id3 = "changeinput2"; var val1 = 0; var val2 = 100;}
    if (this.id == "ComparisonVWAP") {var id1 = "PercentageVWAP"; var id2 = "PercentageVWAP1"; var id3 = "changeinput3"; var val1 = 0; var val2 = 100;}
    if (this.id == "ComparisonRSI") {var id1 = "PercentageRSI"; var id2 = "PercentageRSI1"; var id3 = "changeinput4"; var val1 = 30; var val2 = 70;}
    if (this.id == "ComparisonAverageVolume") {var id1 = "PercentageAverageVolume"; var id2 = "PercentageAverageVolume1"; var id3 = "changeinput5"; var val1 = 0; var val2 = 10000;}
    if (this.id == "ComparisonVolume") {var id1 = "PercentageVolume"; var id2 = "PercentageVolume1"; var id3 = "changeinput13"; var val1 = 0; var val2 = 10000;}
    if (this.id == "ComparisonRelativeVolume") {var id1 = "PercentageRelativeVolume"; var id2 = "PercentageRelativeVolume1"; var id3 = "changeinput6"; var val1 = 0; var val2 = 2;}

    if (this.id == "ComparisonEMA") {var id1 = "PercentageEMA"; var id2 = "PercentageEMA1"; var id3 = "changeinput7"; var val1 = 0; var val2 = 100;}
    if (this.id == "ComparisonOBV") {var id1 = "PercentageOBV"; var id2 = "PercentageOBV1"; var id3 = "changeinput8"; var val1 = 0; var val2 = 100;}
    if (this.id == "ComparisonATR") {var id1 = "PercentageATR"; var id2 = "PercentageATR1"; var id3 = "changeinput9"; var val1 = 0; var val2 = 100;}

    if (this.id == "ComparisonPrevClose") {var id1 = "PercentagePrevClose"; var id2 = "PercentagePrevClose1"; var id3 = "changeinput10"; var val1 = 0; var val2 = 100;}
    if (this.id == "ComparisonLowOfDay") {var id1 = "PercentageLowOfDay"; var id2 = "PercentageLowOfDay1"; var id3 = "changeinput11"; var val1 = 0; var val2 = 100;}
    if (this.id == "ComparisonHighOfDay") {var id1 = "PercentageHighOfDay"; var id2 = "PercentageHighOfDay1"; var id3 = "changeinput12"; var val1 = 0; var val2 = 100;}

    if (this.id == "ComparisonPullbackPct2") {var id1 = "PercentagePullbackPct2"; var id2 = "PercentagePullbackPct2_1"; var id3 = "changeinput14"; var val1 = 0; var val2 = 100;}
    if (this.id == "ComparisonFibGap") {var id1 = "PercentageFibGap"; var id2 = "PercentageFibGap1"; var id3 = "changeinput15"; var val1 = 0; var val2 = 10;}
    if (this.id == "ComparisonMarketCap") {var id1 = "PercentageMarketCap"; var id2 = "PercentageMarketCap1"; var id3 = "changeinput16"; var val1 = 0; var val2 = 100000;}

    if (this.id == "ComparisonPrice") {var id1 = "PercentagePrice"; var id2 = "PercentagePrice1"; var id3 = "changeinputa2";  var val1 = 0; var val2 = 100;}

    var div1 = "<div class = 'inputChange'>";
    var firstInput = "<div class = 'internalinputChange'> <div class ='veritclAlign'> <label id = 'labeltableth'> Lower </label> <input class="+ id1 +" id=" + id1 +" name=" + id1 + " type='text' value=" + val1 + "> </div> </div>";
    var secondInput = "<div class = 'internalinputChange'> <div class ='veritclAlign'> <label id = 'labeltableth'>Upper </label> <input class="+ id2 +" id=" + id2 +" name=" + id2 + " type='text' value=" + val2 + "> </div> </div>";
    var div2 = "</div>";
    var total = div1 + firstInput + secondInput + div2;
    document.getElementById(id3).innerHTML = total;
    document.getElementById(id1).setAttribute("style", "width: 70px; height: 48%;");
    document.getElementById(id2).setAttribute("style", "width: 70px; height: 48%;");

    if (this.id == "ComparisonFastSMA") {var nd1 = "FastSMA"; var nd2 = "FastSMA1"; var nd3 = "nchangeinput1"; var nval1 = 5; var nval2 = 10;}
    if (this.id == "ComparisonSlowSMA") {var nd1 = "SlowSMA"; var nd2 = "SlowSMA1"; var nd3 = "nchangeinput2"; var nval1 = 20; var nval2 = 25;}
    if (this.id == "ComparisonVWAP") {var nd1 = "VWAP"; var nd2 = "VWAP1"; var nd3 = "nchangeinput3"; var nval1 = 5; var nval2 = 10;}
    if (this.id == "ComparisonRSI") {var nd1 = "RSI"; var nd2 = "RSI1"; nd3 = "nchangeinput4"; var nval1 = 14; var nval2 = 20;}
    if (this.id == "ComparisonAverageVolume") {var nd1 = "AverageVolume"; var nd2 = "AverageVolume1"; var nd3 = "nchangeinput5"; var nval1 = 5; var nval2 = 10;}
    if (this.id == "ComparisonVolume") {var nd1 = "Volume"; var nd2 = "Volume1"; var nd3 = "nchangeinput13"; var nval1 = 1; var nval2 = 5;}
    if (this.id == "ComparisonRelativeVolume") {var nd1 = "RelativeVolume"; var nd2 = "RelativeVolume1"; var nd3 = "nchangeinput6"; var nval1 = 5; var nval2 = 10;}

    if (this.id == "ComparisonEMA") {var nd1 = "EMA"; var nd2 = "EMA1"; var nd3 = "nchangeinput7"; var nval1 = 10; var nval2 = 20;}
    if (this.id == "ComparisonOBV") {var nd1 = "OBV"; var nd2 = "OBV1"; var nd3 = "nchangeinput8"; var nval1 = 10; var nval2 = 20;}
    if (this.id == "ComparisonATR") {var nd1 = "ATR"; var nd2 = "ATR1"; var nd3 = "nchangeinput9"; var nval1 = 14; var nval2 = 20;}

    if (this.id == "ComparisonPrevClose") {var nd1 = "PrevClose"; var nd2 = "PrevClose1"; var nd3 = "nchangeinput10"; var nval1 = 0; var nval2 = 1000;}
    if (this.id == "ComparisonLowOfDay") {var nd1 = "LowOfDay"; var nd2 = "LowOfDay1"; var nd3 = "nchangeinput11"; var nval1 = 0; var nval2 = 1000;}
    if (this.id == "ComparisonHighOfDay") {var nd1 = "HighOfDay"; var nd2 = "HighOfDay1"; var nd3 = "nchangeinput12"; var nval1 = 0; var nval2 = 1000;}

    if (this.id == "ComparisonPullbackPct2") {var nd1 = "PullbackPct2"; var nd2 = "PullbackPct2_1"; var nd3 = "nchangeinput14"; var nval1 = 0; var nval2 = 100;}
    if (this.id == "ComparisonFibGap") {var nd1 = "FibGap"; var nd2 = "FibGap1"; var nd3 = "nchangeinput15"; var nval1 = 0; var nval2 = 10;}
    if (this.id == "ComparisonMarketCap") {var nd1 = "MarketCap"; var nd2 = "MarketCap1"; var nd3 = "nchangeinput16"; var nval1 = 0; var nval2 = 100000;}

    if (this.id == "ComparisonPrice") {var nd1 = "Pricelevel"; var nd2 = "Pricelevel1"; nd3 = "nchangeinputa2"; var nval1 = 0; var nval2 = 1000;}

    var ndaydiv1 = "<div class = 'inputChangediv'>";
    var ndayinput1 = "<div class = 'internalinputChange'> <div class ='veritclAlign'> <label id = 'labeltableth'> Lower </label> <input class= " + nd1 + " id=" + nd1 + " name=" + nd1 +" type='text' value=" + nval1 + "> </div> </div>";
    var ndayinput2 = "<div class = 'internalinputChange'> <div class ='veritclAlign'> <label id = 'labeltableth'> Upper </label> <input class= " + nd2 + " id=" + nd2 + " name=" + nd2 +" type='text' value=" + nval2 + "> </div> </div>";
    var ndaydiv2 = "</div>";
    var ntotal = ndaydiv1 + ndayinput1 + ndayinput2 + ndaydiv2;
    document.getElementById(nd3).innerHTML = ntotal;
    document.getElementById(nd1).setAttribute("style", "width: 70px; height: 48%;");
    document.getElementById(nd2).setAttribute("style", "width: 70px; height: 48%;");

  } else {

    if (this.id == "ComparisonFastSMA") {var id1 = "PercentageFastSMA"; var id2 = "PercentageFastSMA1"; var id3 = "changeinput1";}
    if (this.id == "ComparisonSlowSMA") {var id1 = "PercentageSlowSMA"; var id2 = "PercentageSlowSMA1"; var id3 = "changeinput2";}
    if (this.id == "ComparisonVWAP") {var id1 = "PercentageVWAP"; var id2 = "PercentageVWAP1"; var id3 = "changeinput3";}
    if (this.id == "ComparisonRSI") {var id1 = "PercentageRSI"; var id2 = "PercentageRSI1"; var id3 = "changeinput4";}
    if (this.id == "ComparisonAverageVolume") {var id1 = "PercentageAverageVolume"; var id2 = "PercentageAverageVolume1"; var id3 = "changeinput5";}
    if (this.id == "ComparisonVolume") {var id1 = "PercentageVolume"; var id2 = "PercentageVolume1"; var id3 = "changeinput13";}
    if (this.id == "ComparisonRelativeVolume") {var id1 = "PercentageRelativeVolume"; var id2 = "PercentageRelativeVolume1"; id3 = "changeinput6";}

    if (this.id == "ComparisonEMA") {var id1 = "PercentageEMA"; var id2 = "PercentageEMA1"; var id3 = "changeinput7";}
    if (this.id == "ComparisonOBV") {var id1 = "PercentageOBV"; var id2 = "PercentageOBV1"; var id3 = "changeinput8";}
    if (this.id == "ComparisonATR") {var id1 = "PercentageATR"; var id2 = "PercentageATR1"; var id3 = "changeinput9";}

    if (this.id == "ComparisonPrevClose") {var id1 = "PercentagePrevClose"; var id2 = "PercentagePrevClose1"; var id3 = "changeinput10";}
    if (this.id == "ComparisonLowOfDay") {var id1 = "PercentageLowOfDay"; var id2 = "PercentageLowOfDay1"; var id3 = "changeinput11";}
    if (this.id == "ComparisonHighOfDay") {var id1 = "PercentageHighOfDay"; var id2 = "PercentageHighOfDay1"; var id3 = "changeinput12";}

    if (this.id == "ComparisonPullbackPct2") {var id1 = "PercentagePullbackPct2"; var id2 = "PercentagePullbackPct2_1"; var id3 = "changeinput14";}
    if (this.id == "ComparisonFibGap") {var id1 = "PercentageFibGap"; var id2 = "PercentageFibGap1"; var id3 = "changeinput15";}
    if (this.id == "ComparisonMarketCap") {var id1 = "PercentageMarketCap"; var id2 = "PercentageMarketCap1"; var id3 = "changeinput16";}

    if (this.id == "ComparisonPrice") {var id1 = "PercentagePrice"; var id2 = "PercentagePrice1"; id3 = "changeinputa2";}

    if (document.getElementById(id2) != null) {
      var firstInput = "<div class = 'internalinputChange'> <input class="+ id1 +" id=" + id1 +" name=" + id1 + " type='text' value='' display: none;> </div>";
      document.getElementById(id3).innerHTML = firstInput;
      document.getElementById(id1).setAttribute("style", "width: 140px; height: 100%;");

      if (this.id == "ComparisonFastSMA") {var nd1 = "FastSMA"; nd3 = "nchangeinput1";}
      if (this.id == "ComparisonSlowSMA") {var nd1 = "SlowSMA"; nd3 = "nchangeinput2";}
      if (this.id == "ComparisonVWAP") {var nd1 = "VWAP"; nd3 = "nchangeinput3";}
      if (this.id == "ComparisonRSI") {var nd1 = "RSI"; nd3 = "nchangeinput4";}
      if (this.id == "ComparisonAverageVolume") {var nd1 = "AverageVolume"; nd3 = "nchangeinput5";}
      if (this.id == "ComparisonVolume") {var nd1 = "Volume"; nd3 = "nchangeinput13";}
      if (this.id == "ComparisonRelativeVolume") {var nd1 = "RelativeVolume"; nd3 = "nchangeinput6";}

      if (this.id == "ComparisonEMA") {var nd1 = "EMA"; nd3 = "nchangeinput7";}
      if (this.id == "ComparisonOBV") {var nd1 = "OBV"; nd3 = "nchangeinput8";}
      if (this.id == "ComparisonATR") {var nd1 = "ATR"; nd3 = "nchangeinput9";}

      if (this.id == "ComparisonPrevClose") {var nd1 = "PrevClose"; nd3 = "nchangeinput10";}
      if (this.id == "ComparisonLowOfDay") {var nd1 = "LowOfDay"; nd3 = "nchangeinput11";}
      if (this.id == "ComparisonHighOfDay") {var nd1 = "HighOfDay"; nd3 = "nchangeinput12";}

      if (this.id == "ComparisonPullbackPct2") {var nd1 = "PullbackPct2"; nd3 = "nchangeinput14";}
      if (this.id == "ComparisonFibGap") {var nd1 = "FibGap"; nd3 = "nchangeinput15";}
      if (this.id == "ComparisonMarketCap") {var nd1 = "MarketCap"; nd3 = "nchangeinput16";}

      if (this.id == "ComparisonPrice") {var nd1 = "Pricelevel"; nd3 = "nchangeinputa2";}

      var ndayinput1 = "<div class = 'internalinputChange'> <input class="+ nd1 +" id=" + nd1 +" name=" + nd1 + " type='text' value=''> </div>";
      document.getElementById(nd3).innerHTML = ndayinput1;
      document.getElementById(nd1).setAttribute("style", "width: 140px; height: 100%;");
    }

    if (this.id == "ComparisonFastSMA") {var nd1 = "FastSMA"; var id1 = "PercentageFastSMA";}
    if (this.id == "ComparisonSlowSMA") {var nd1 = "SlowSMA"; var id1 = "PercentageSlowSMA";}
    if (this.id == "ComparisonVWAP") {var nd1 = "VWAP"; var id1 = "PercentageVWAP";}
    if (this.id == "ComparisonRSI") {var nd1 = "RSI"; id1 = "PercentageRSI";}
    if (this.id == "ComparisonAverageVolume") {var nd1 = "AverageVolume"; var id1 = "PercentageAverageVolume";}
    if (this.id == "ComparisonVolume") {var nd1 = "Volume"; var id1 = "PercentageVolume";}
    if (this.id == "ComparisonRelativeVolume") {var nd1 = "RelativeVolume"; var id1 = "PercentageRelativeVolume";}

    if (this.id == "ComparisonEMA") {var nd1 = "EMA"; var id1 = "PercentageEMA";}
    if (this.id == "ComparisonOBV") {var nd1 = "OBV"; var id1 = "PercentageOBV";}
    if (this.id == "ComparisonATR") {var nd1 = "ATR"; var id1 = "PercentageATR";}

    if (this.id == "ComparisonPrevClose") {var nd1 = "PrevClose"; var id1 = "PercentagePrevClose";}
    if (this.id == "ComparisonLowOfDay") {var nd1 = "LowOfDay"; var id1 = "PercentageLowOfDay";}
    if (this.id == "ComparisonHighOfDay") {var nd1 = "HighOfDay"; var id1 = "PercentageHighOfDay";}

    if (this.id == "ComparisonPullbackPct2") {var nd1 = "PullbackPct2"; var id1 = "PercentagePullbackPct2";}
    if (this.id == "ComparisonFibGap") {var nd1 = "FibGap"; var id1 = "PercentageFibGap";}
    if (this.id == "ComparisonMarketCap") {var nd1 = "MarketCap"; var id1 = "PercentageMarketCap";}

    if (this.id == "ComparisonPrice") {var nd1 = "Pricelevel";}

    if (this.value == "Not used") {
        document.getElementById(nd1).style.display = "none";
        document.getElementById(id1).style.display = "none";
    } else {
      document.getElementById(nd1).style.display  = "block";
      document.getElementById(id1).style.display = "block";
    }

  }
}


/*
var cell = document.createElement("button");
cell.innerHTML = "Add";
cell.setAttribute("id", "buttontobuy" + 1); //cell.setAttribute("id", "buttontobuy" + i);
cell.setAttribute("style", "width: 100%;");
document.getElementById("demotest").appendChild(cell); //row.appendChild(cell);
*/

/*
var nelm =  0; //number of elements
cell.onclick = function () {
  event.preventDefault();
  var currentId = this.id;
  console.log(nelm, " tuturu");

  var stockName = "ELFEO";//document.getElementById(currentId).parentElement.children[1].innerHTML;
  var longshort = "LONG" //document.getElementsByClassName("LongShort")[0].value";
  var parentChildren = 7 //document.getElementById("appendFormIndicator").children.length;
  var actualPrice = 20 //document.getElementById(currentId).parentElement.children[2].innerHTML;
  var supporT = (parseFloat(actualPrice) * 0.95).toFixed(2) //(actualPrice)toFixed(2)
  var resistencE = (parseFloat(actualPrice) * 1.05).toFixed(2) //(actualPrice)toFixed(2)
  var divBuySell = "<div class = 'buysell'>";
  var divStock = "<div class = 'makeColum'> <label class='labelbuysell'>Stock</label> <input type='text' value=" +stockName + " class = 'buysellinput'></div>";
  var divNShare = "<div class = 'makeColum'> <label class='labelbuysell'>N Share</label> <input type='number' value='1' class = 'buysellinput'></div>";
  var divBrackteLimit = "<div class = 'makeColum'> <label class='labelbuysell'>Type</label> <select class = 'buysellSelect' id = 'changevalues" + nelm + "'> <option value='bracket' selected=''>Bracket </option> <option value='limit'>Limit</option> </select> </div>";
  var divBuySell = "<div class = 'makeColum'> <label class='labelbuysell'>Side</label> <select class = 'buysellSelect'> <option value='long' selected=''>Long </option> <option value='short'>Short</option> </select> </div>";
  var thecurrentPrice = "<div class = 'makeColum'> <label class='labelbuysell'>Price</label> <input type='number' value='" + actualPrice + "' class = 'buysellinput'></div>";

  var supportLevel = "<div class = 'makeColum'> <label class='labelbuysell'>Support</label> <input type='number' value='' class = 'buysellinput' id = 'support" + nelm + "'></div>";
  var StopLoss = "<div class = 'makeColum'> <label class='labelbuysell'>StopLoss(%)</label> <input type='number' value='10' class = 'buysellinput'></div>";
  var resistenceLevel = "<div class = 'makeColum'> <label class='labelbuysell'>Resistence</label> <input type='number' value='' class = 'buysellinput' id = 'resistence" + nelm + "'></div>";
  var ema = "<div class = 'makeColum'> <label class='labelbuysell'>EMA</label> <input type='number' value='13' class = 'buysellinput'></div>";
  var send = "<div class = 'makeColum'> <label class='labelbuysell'>Order</label> <button class = 'buysellinput' id = 'sendToFlask" + parentChildren + "'>Send</button></div>";
  var send1 = "<div class = 'makeColum'> <label class='labelbuysell'>Order</label> <button class = 'buysellinput'>Send</button></div>";
  var divBuySellClose = "</div>";
  var elementToAppend =  divStock + divNShare + divBrackteLimit + divBuySell + thecurrentPrice + supportLevel + StopLoss + resistenceLevel + ema + send; // + send1;
  myelement = document.createElement("DIV");
  myelement.setAttribute("class", "buysell");
  myelement.innerHTML = elementToAppend;
  document.getElementById("elfeo").appendChild(myelement);

  document.getElementById('changevalues' + nelm).addEventListener("change", changeOptions);
  nelm = nelm + 1;


}

*/

function changeOptions() {
  if ( parseInt(this.id.slice(-1)) >= 0) { idnumber = this.id.slice(-1);}
  if ( parseInt(this.id.slice(-2)) >= 0) { idnumber = this.id.slice(-2);}
  if ( parseInt(this.id.slice(-3)) >= 0) { idnumber = this.id.slice(-3);}
  if ( parseInt(this.id.slice(-4)) >= 0) { idnumber = this.id.slice(-4);}
  if ( parseInt(this.id.slice(-5)) >= 0) { idnumber = this.id.slice(-5);}
  if ( parseInt(this.id.slice(-6)) >= 0) { idnumber = this.id.slice(-6);}
  if ( parseInt(this.id.slice(-7)) >= 0) { idnumber = this.id.slice(-7);}

  var supportid = "support" + idnumber; 
  var resistenceid = "resistence" + idnumber;
  console.log(this.id, this.id.slice(-1), supportid, " ... ", resistenceid);
  //Now change base in value
  if ( document.getElementById(this.id).value == "bracket") {

    if ( document.getElementById(supportid).parentElement.style.display != "block" ) {
      document.getElementById(supportid).parentElement.style.display = "block";
    }
    if (document.getElementById(resistenceid).parentElement.style.display = "block" ) {
      document.getElementById(resistenceid).parentElement.style.display = "block";
    }
    document.getElementsByClassName("secondPart")[0].style.display = "block";
    
  } else {
    document.getElementById(supportid).parentElement.style.display = "none";
    document.getElementById(resistenceid).parentElement.style.display = "none";
    document.getElementsByClassName("secondPart")[0].style.display = "none";
  }
}



function SupportResistenceChange() {
      var x = parseFloat(document.getElementsByClassName("buysellinput")[2].value);
      console.log(x, "*****");
      try {
        var theside = document.getElementsByClassName("buysellSelect")[1].value;
        if ( theside == "long") {          
          var myelementtouse = document.getElementsByClassName("buysellinput");
          //Support
          var supportPercentage = parseFloat(document.getElementsByClassName("percentageClass")[0].value);
          document.getElementsByClassName("buysellinput")[3].value = (x * (1.0 - supportPercentage / 100.0)).toFixed(2);  
          myelementtouse[3].style.background = '#abebae';

          //Resistence
          var resistencePercentage = parseFloat(document.getElementsByClassName("percentageClass")[1].value);
          document.getElementsByClassName("buysellinput")[5].value = (x * (1.0 + resistencePercentage / 100.0)).toFixed(2);
          myelementtouse[5].style.background = '#abebae';

          setTimeout(function(){
            myelementtouse[3].style.background = "#ffffff";
            myelementtouse[5].style.background = "#ffffff";
          }, 1000);

        } else {
          var myelementtouse = document.getElementsByClassName("buysellinput");
          //Support
          var supportPercentage = parseFloat(document.getElementsByClassName("percentageClass")[0].value);
          document.getElementsByClassName("buysellinput")[3].value = (x * (1.0 + supportPercentage / 100.0)).toFixed(2);  
          myelementtouse[3].style.background = '#abebae';

          //Resistence
          var resistencePercentage = parseFloat(document.getElementsByClassName("percentageClass")[1].value);
          document.getElementsByClassName("buysellinput")[5].value = (x * (1.0 - resistencePercentage / 100.0)).toFixed(2);
          myelementtouse[5].style.background = '#abebae';

          setTimeout(function(){
            myelementtouse[3].style.background = "#ffffff";;
            myelementtouse[5].style.background = "#ffffff";;
          }, 2000);

        }
        

      } catch ( err ) {
        console.log(err.message);

      }
      
}


function formatInstrument() {
    var totalE = document.getElementById("addcustomfields").children.length;
    var myArray = [];
    for (let __ = 0; __ < totalE; __++){
      var manualticker = document.getElementById("addcustomfields").children[__];
      var singleTicker = manualticker.children[0].children[1].value;
      var singleCusip = manualticker.children[1].children[1].value;
      myArray.push({"ticker": singleTicker, "cusip": singleCusip})
    }
    myArray = {"securities": myArray};
    return myArray;
}