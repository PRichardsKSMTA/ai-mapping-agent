from utils.excel_utils import excel_to_json

records, columns = excel_to_json("C:\\Users\\pete.richards\\OneDrive - KSM Business Services Inc\\Desktop\\KSM Trial Balance 3.31.2025.xlsx")
print("Detected columns:", columns)
print("First record sample:", records[0])