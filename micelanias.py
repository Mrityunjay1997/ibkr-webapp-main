import time
import os
import json
import pandas as pd
import numpy as np

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from datetime import date


class getPdf:
    def __init__(self):
        """
		self.ARKK = "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv"
		self.ARKQ = "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKQ_HOLDINGS.csv"
		self.ARKW = "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKW_HOLDINGS.csv"
		self.ARKG = "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKG_HOLDINGS.csv"
		self.ARKF = "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKF_HOLDINGS.csv"
		self.ARKX = "https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_ARKX_HOLDINGS.csv"
		"""
        self.ARKK = "https://ark-funds.com/funds/arkk/"
        self.ARKQ = "https://ark-funds.com/funds/arkq/"
        self.ARKW = "https://ark-funds.com/funds/arkw/"
        self.ARKG = "https://ark-funds.com/funds/arkg/"
        self.ARKF = "https://ark-funds.com/funds/arkf/"
        self.ARKX = "https://ark-funds.com/funds/arkx/"

        self.thefilesDate = None
        self.dayfolder = date.today().strftime("%Y-%m-%d")
        self.rootdirectory = "dates"
        self.thefiles = self.AllFiles()
        self.createFolder()
        self.thefilesDay = self.AllFilesDay()

    def AllFiles(self):
        return os.listdir(self.rootdirectory)

    def AllFilesDay(self):
        return os.listdir(self.rootdirectory + "\\" + self.dayfolder)

    def checkIfExistFile(self, file, longurl):
        # Set the parameter option to download file
        import os
        ROOT_DIR = os.path.abspath(os.curdir)
        options = Options()

        options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": os.path.join(
                    ROOT_DIR, self.rootdirectory, self.dayfolder
                ),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "plugins.always_open_pdf_externally": True,
            }
        )

        service = Service(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=service, options=options)
        # Get Data
        counter = 0
        # Wait until the file is downloaded
        nfile = len(self.AllFilesDay())
        nfile1 = nfile
        while nfile == nfile1:
            self.thefilesDay = self.AllFilesDay()
            nfile1 = len(self.thefilesDay)
            if file in self.thefilesDay:
                print("file {} exist in the folder. Sleep 2 to second to finish download".format(file), "\n")
                time.sleep(2)
            if counter == 0:
                driver.get(longurl)
                print(longurl, "++++++++++++++")
                time.sleep(3)
                # <a class="more-link" id="close-board-popup" href="#">Skip</a>
                try:
                    myskip = driver.find_element(By.CSS_SELECTOR, '.more-link')
                    driver.execute_script('arguments[0].click()', myskip)
                except Exception as e:
                    print(e)
                time.sleep(3)
                myclick = driver.find_element(By.CSS_SELECTOR,
                                              '.b-table__link:nth-child(2)')  # class="b-table__link fund-generate-holdings-csv" #button.fund-generate-holdings-pdf
                print(myclick, " 12354")
                time.sleep(4)
                driver.execute_script('arguments[0].click()', myclick)
                print("File: {} does not exist. Wait 4 second".format(file))
                time.sleep(5)
            # time.sleep(6)
            # driver.quit()
            # break
            time.sleep(1)
            counter += 1
            if counter % 15 == 0:
                print("Clicking again")
                driver.execute_script('arguments[0].click()', myclick)
            """
			if counter > 0 and nfile == nfile1:
				#driver.execute_script('arguments[0].click()', myclick)
				time.sleep(6)
			counter += 1
			if counter == 16:
				print("Maximum Time to wait 16 seconds. Stop Download", "\n")
			"""

        driver.quit()

    def chekAllFiles(self):
        allfilesName = ["ARK_INNOVATION_ETF_ARKF_HOLDINGS.csv", "ARK_INNOVATION_ETF_ARKG_HOLDINGS.csv",
                        "ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv", "ARK_INNOVATION_ETF_ARKQ_HOLDINGS.csv",
                        "ARK_INNOVATION_ETF_ARKW_HOLDINGS.csv", "ARK_INNOVATION_ETF_ARKX_HOLDINGS.csv"]
        # allfilesName = ["ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv", "ARK_AUTONOMOUS_TECHNOLOGY_&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv", "ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.csv", "ARK_GENOMIC_REVOLUTION_MULTISECTOR_ETF_ARKG_HOLDINGS.csv", "ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv", "ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.csv"]
        ROOT_DIR = os.path.abspath(os.curdir)
        url_ = ROOT_DIR + "\\" + self.rootdirectory + "\\" + self.dayfolder
        mydir = os.listdir(url_)

        fullurl = [self.ARKK, self.ARKQ, self.ARKW, self.ARKG, self.ARKF, self.ARKX]
        shorturl = [self.ARKK.split("/")[-1], self.ARKQ.split("/")[-1], self.ARKW.split("/")[-1],
                    self.ARKG.split("/")[-1], self.ARKF.split("/")[-1], self.ARKX.split("/")[-1]]

        for i, j, k in zip(shorturl, fullurl, allfilesName):
            if k in mydir:
                print("Document Already downloaded: ", k)
            else:
                print(i, "--", j, "--", k, "___________--__________")
                self.checkIfExistFile(i, j)

        print("__________________________222222222222222222222222________________________________")

        mydir = os.listdir(url_)
        print(mydir)

        for i in mydir:
            if i in allfilesName:
                print("Document Already in the folder")
            else:
                print("Changing Name")
                tickerList = i.split("HOLDINGS")[0] + "HOLDINGS.csv"
                # print(url_ +"\\" + i, "________$$$$$_______", "\n", url_ +"\\" + "ARK_AUTONOMOUS_TECHNOLOGY_&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv")
                getResultTicker = i.split("_")[-2]
                if getResultTicker == "ARKK": os.rename(url_ + "\\" + i,
                                                        url_ + "\\" + "ARK_INNOVATION_ETF_ARKK_HOLDINGS.csv");print(
                    "____1____")
                if getResultTicker == "ARKQ": os.rename(url_ + "\\" + i,
                                                        url_ + "\\" + "ARK_AUTONOMOUS_TECHNOLOGY_&_ROBOTICS_ETF_ARKQ_HOLDINGS.csv"); print(
                    "____1____")
                if getResultTicker == "ARKW": os.rename(url_ + "\\" + i,
                                                        url_ + "\\" + "ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.csv"); print(
                    "____1____")
                if getResultTicker == "ARKG": os.rename(url_ + "\\" + i,
                                                        url_ + "\\" + "ARK_GENOMIC_REVOLUTION_MULTISECTOR_ETF_ARKG_HOLDINGS.csv"); print(
                    "____1____")
                if getResultTicker == "ARKF": os.rename(url_ + "\\" + i,
                                                        url_ + "\\" + "ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.csv"); print(
                    "____1____")
                if getResultTicker == "ARKX": os.rename(url_ + "\\" + i,
                                                        url_ + "\\" + "ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.csv")

    def createFolder(self):
        if not self.dayfolder in self.thefiles:
            os.mkdir(self.rootdirectory + "\\" + self.dayfolder)
            print("Creating New Folder: {}".format(self.dayfolder))
        else:
            print("Folder {} Exist".format(self.dayfolder))
        return self.rootdirectory + "\\" + self.dayfolder


class ComparePdf:
    def __init__(self, url):
        self.a = 1
        self.url = url
        self.fileDirectory = {}
        self.getFolders()
        self.assetsToBuyBellIb = []
        self.uniqueCusip = []
        self.fullTickers = []

    def getFolders(self):
        mylist = os.listdir(self.url)
        # print("______", mylist)
        mylist = sorted(mylist, reverse=True)[:2]
        for i in mylist:
            subdir = os.path.join(self.url, i)
            for j in os.listdir(subdir):
                rootfile = os.path.join(subdir, j)
                if not j in self.fileDirectory:
                    self.fileDirectory[j] = []
                self.fileDirectory[j].append(rootfile)

    # print("\n \n ____________",self.fileDirectory)

    def fromPdfToPandas(self, etf, position):
        dta = self.fileDirectory[etf]
        # print(dta, "__----__", position)
        tt = pd.read_csv(dta[position])
        if np.isnan(tt.iloc[-1][1]) == True and np.isnan(tt.iloc[-1][2]) == True:
            tt = tt.iloc[:-2]
        tt = tt.copy().set_index("cusip")
        return tt

    def IntersectionDifferece(self, etf):
        result = self.fromPdfToPandas(etf, 0)
        # df1 Represent the most recent data
        df1 = result  # Data Frame
        result1 = self.fromPdfToPandas(etf, 1)
        # df2 represent the second most recent data
        df2 = result1  # Data Frame
        # print(df1)
        # print(df2, "\n \n \n")

        difference = df1.index.difference(df2.index)  # pt -pt-1 (Most recent data - second most recent data)
        difference1 = df2.index.difference(df1.index)  # pt-1 - pt (Second most updated data - Most updated data)
        # Convert Shares to numeric (Integer)
        df2["shares"] = [int(i.replace(",", "")) for i in df2["shares"].values]
        df1["shares"] = [int(i.replace(",", "")) for i in df1["shares"].values]
        # print(df1["Shares"][0:4], "_ __ _", df1["Shares"][0] + df1["Shares"][1])

        # Now calculate the difference and intersection. indexintersection = Stocks in common. indexdifference=a new stock bought that previously was not in the portfolio
        indexintersection = df1.index.intersection(df2.index)  # Get The intersection. A Intersection B
        indexdifference = df1.index.difference(df2.index)  # Get difference pt - pt-1. A-B
        indexdifference1 = df2.index.difference(df1.index)  # Get difference pt-1 - pt. B-A
        totaldifference = indexdifference.union(indexdifference1)  # Get A-B+ B-A
        # print(df1.columns)

        assetsToBuy = []  # Create a empty list 67066G104
        cusipEtf = []
        tickerEtf = []
        # First add the union of difference (indexdifference, new stocks (Signal buy)) and (indexdifference1, stock solds)
        # pd.set_option("display.max_rows", None, "display.max_columns", None)
        if len(totaldifference) > 0:
            # if len(df1.index) >0:
            for ii in totaldifference:
                # for ii in df1.index:
                if ii in df1.index:
                    newbuy = df1.loc[ii]
                elif ii in df2.index:
                    newbuy = df2.loc[ii]

                if ii in df1.index:
                    assetsToBuy.append({"cusip": ii, "ticker": str(newbuy["ticker"]), "change": int(newbuy["shares"])})
                # print("Comproooooooo ", ii, newbuy["Ticker"], int(newbuy["Shares"]), etf)
                elif ii in df2.index:
                    assetsToBuy.append({"cusip": ii, "ticker": str(newbuy["ticker"]), "change": -int(newbuy["shares"])})
                # print("NO SUCCEDE", ii, newbuy["Ticker"], -int(newbuy["Shares"]), etf)
                if ii not in self.uniqueCusip:
                    self.uniqueCusip.append(ii)
                    self.fullTickers.append(str(newbuy["ticker"]))

                if ii not in cusipEtf:
                    cusipEtf.append(ii)
                    tickerEtf.append(str(newbuy["ticker"]))

        # Second Get the inttersection
        df1 = df1.copy().reindex(indexintersection)
        df2 = df2.copy().reindex(indexintersection)
        # print(df1.index, "\n", df2.index)
        tti = pd.DataFrame([df1["shares"], df2["shares"]])
        # print(tti)
        df1["SharesChange"] = df1["shares"] - df2["shares"]
        # print(df1[["SharesChange", "shares"]], "___")

        # See which instruments were reballance
        assets = df1[df1.SharesChange != 0]
        for i, j in assets.iterrows():
            assetsToBuy.append({"cusip": i, "ticker": str(j["ticker"]), "change": int(j["SharesChange"])})
            if i not in self.uniqueCusip:
                self.uniqueCusip.append(i)
                self.fullTickers.append(str(j["ticker"]))
            if i not in cusipEtf:
                cusipEtf.append(i)
                tickerEtf.append(str(j["ticker"]))

        assetToReturn = {etf.split("_")[-2]: assetsToBuy, "cusip": cusipEtf, "ticker": tickerEtf}
        # print(assetToReturn)
        print(tickerEtf)
        return assetToReturn

    def AllResults(self, etf):
        result = self.fromPdfToPandas(etf, 0)
        # df1 Represent the most recent data
        df1 = result  # Data Frame

        df1["shares"] = [int(i.replace(",", "")) for i in df1["shares"].values]
        # print(df1["Shares"][0:4], "_ __ _", df1["Shares"][0] + df1["Shares"][1])

        assetsToBuy = []  # Create a empty list 67066G104
        cusipEtf = []
        tickerEtf = []

        if len(df1.index) > 0:
            for ii in df1.index:
                if ii in df1.index:
                    newbuy = df1.loc[ii]
                elif ii in df2.index:
                    newbuy = df2.loc[ii]

                if ii in df1.index:
                    assetsToBuy.append({"cusip": ii, "ticker": str(newbuy["ticker"]), "change": int(newbuy["shares"])})
                # print("Comproooooooo ", ii, newbuy["Ticker"], int(newbuy["Shares"]), etf)

                if ii not in self.uniqueCusip:
                    self.uniqueCusip.append(ii)
                    self.fullTickers.append(str(newbuy["ticker"]))

                if ii not in cusipEtf:
                    cusipEtf.append(ii)
                    tickerEtf.append(str(newbuy["ticker"]))

        assetToReturn = {etf.split("_")[-2]: assetsToBuy, "cusip": cusipEtf, "ticker": tickerEtf}
        # print(assetToReturn)
        print(tickerEtf)
        return assetToReturn

    def dictionaryToIB(self):
        condition = True
        counter = 0
        listEtf = list(self.fileDirectory.keys())
        while condition:
            try:
                myresult = self.IntersectionDifferece(listEtf[counter])
                print(list(myresult.keys()))
                print(myresult)
                result = json.dumps(myresult)
                # print(self.uniqueCusip, len(self.fullTickers))
                yield f"data:{result}\n\n"
            except Exception as e:
                print(e)
                yield f"data: finished\n\n"
                break
            counter += 1

    def dictionaryToIB1(self):
        condition = True
        counter = 0
        listEtf = list(self.fileDirectory.keys())
        # print(listEtf, " WWWW")
        for i in listEtf:
            myresult = self.IntersectionDifferece(i)

    # print(self.fullTickers, len(self.fullTickers))
    # print(i)


def allData(urlroot):
    # urlroot = "C:/Users/Utente/Desktop/aplicationupwork/finalapp/app/dates/2021-11-05/"
    files = os.listdir(urlroot)
    # print(files)
    data = {}
    # pd.DataFrame(columns =)
    counter = 0
    for i in files:
        counter += len(pd.read_csv(urlroot + i).index)
        if len(data) == 0:
            df = pd.read_csv(urlroot + i).iloc[:-1, :]
            df["shares"] = [int(i.replace(",", "")) for i in df["shares"].values]
            data["allcsv"] = df
        # print(data["allcsv"])
        else:
            df = pd.read_csv(urlroot + i).iloc[:-1, :]
            df["shares"] = [int(i.replace(",", "")) for i in df["shares"].values]
            data["allcsv"] = data["allcsv"].append(df, ignore_index=True)

    # thedata =data["allcsv"].groupby(["cusip", "ticker"], as_index=False).sum()
    # thedata = thedata.set_index("cusip")
    # print("N rows: ", len(thedata.index))
    return data["allcsv"]


def dataProcessing():
    URL = os.listdir(os.path.abspath(os.curdir) + "\\" + "dates")

    new = sorted(URL, reverse=True)[0]
    old = sorted(URL, reverse=True)[1]

    urlnew = os.path.abspath(os.curdir) + "\\" + "dates" + "\\" + new + "\\"
    urlold = os.path.abspath(os.curdir) + "\\" + "dates" + "\\" + old + "\\"

    newdata = allData(urlnew)
    olddata = allData(urlold)

    alldata = {}
    ###Current Ticker###
	# [{'cusip': '88160R101', 'ticker': 'TSLA', 'change': -5636}
    for k, i in newdata.iterrows():
        if i["cusip"] not in alldata:
            # print(i["ticker"])
            if i["cusip"] != "nan":
                alldata[i["cusip"]] = {"cusip": i["cusip"], "ticker": i["ticker"], "change": i["shares"]}
            else:
                print(i["shares"])
        else:
            if i["cusip"] != "nan":
                alldata[i["cusip"]]["change"] = alldata[i["cusip"]]["change"] + i["shares"]
				# print(alldata[i["ticker"]]["shares"], "*****")
				# print("_______________", i["ticker"])
            else:
                print(i["shares"])
	# print(alldata)

    ###Old ticker###
    for k, i in olddata.iterrows():
        if i["cusip"] not in alldata:
            # print(i["ticker"])
            if i["cusip"] != "nan":
                print(i["ticker"])
                alldata[i["cusip"]] = {"cusip": i["cusip"], "ticker": i["ticker"], "change": -i["shares"]}
            else:
                print(i["shares"])
        else:
            if i["cusip"] != "nan":
                alldata[i["cusip"]]["change"] = alldata[i["cusip"]]["change"] - i["shares"]
            else:
                print(i["shares"])

	# print(list(alldata.values()))
    cusip = []
    ticker = []
    for i in alldata.values():
        cusip.append(i["cusip"])
        ticker.append(i["ticker"])

    myresult = {"All Funds": list(alldata.values()), "cusip": cusip, "ticker": ticker}

	# print([i for i in alldata.values() if i["shares"] > 0])
    return myresult


# replace(/\bNaN\b/g, "null"))
# etf ='ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.pdf' # 'ARK_FINTECH_INNOVATION_ETF_ARKF_HOLDINGS.pdf' #'ARK_GENOMIC_REVOLUTION_MULTISECTOR_ETF_ARKG_HOLDINGS.pdf' 'ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf'  'ARK_NEXT_GENERATION_INTERNET_ETF_ARKW_HOLDINGS.pdf'  'ARK_SPACE_EXPLORATION_&_INNOVATION_ETF_ARKX_HOLDINGS.pdf'
"""
rootdir = "dates"
casa = ComparePdf(rootdir)
ComparePdf(rootdir).getFolders()
testing =list(casa.fileDirectory.keys())
print(testing)
for etfDict in testing:
	try:
		print("________________________________________________________________", "\n", etfDict)
		myresult = casa.IntersectionDifferece(etfDict)
		etf__ = etfDict.split(".")[0]  
	except Exception as e:
		print(e)
"""

# print(casa.IntersectionDifferece(etf))
# casa.dictionaryToIB1()


# tio = getPdf()
# tio.createFolder()
# tio.chekAllFiles()
# tio.DownloadpdfFile(tio.ARKK)
# tio.AllFiles()
# tio.checkIfExistFile("ARK_INNOVATION_ETF_ARKK_HOLDINGS.pdf")
# tio.chekAllFiles()