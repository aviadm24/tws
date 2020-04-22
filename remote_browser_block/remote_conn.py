import wmi
import socket
ipaddress = socket.gethostbyname(socket.gethostname())
print("ipaddress: ", ipaddress)
my_ip = '192.168.1.13'
ip = '10.1.89.103'
# https://stackoverflow.com/questions/18961213/how-to-connect-to-a-remote-windows-machine-to-execute-commands-using-python
c = wmi.WMI('vmgen403.speedytradingservers.com:33403', user='Administrator', password='yosYOS1234')
# c = wmi.WMI(ip, user=r'Administrator', password='yosYOS1234')
process_id, return_value = c.Win32_Process.Create(CommandLine="cmd.exe /c  dir")
print("p: ", process_id)
print("r: ", return_value)