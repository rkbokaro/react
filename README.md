Working- d-code-tpc and d-satsreact  for track diagram

 HttpURLConnection conn = (HttpURLConnection) url
.openConnection();   ---> this code for deployment

HttpURLConnection conn = (HttpURLConnection)url.openConnection( new
Proxy(Proxy.Type.HTTP, new InetSocketAddress("172.16.1.61", 8080)) ); this code for developemnt


some times application run with https and some time http


 .\mvnw clean install  



 logfile of netbeans------we can see the output of console in spring boot ---same is available in log file name "messages" of log of elastic netbeans. 



differences between mvn clean package and mvn clean install

 package will add packaged jar or war to your target folder, We can check it when, we empty the target folder (using mvn clean) and then run mvn package.
install will do all the things that package does, additionally it will add packaged jar or war in local repository as well. We can confirm it by checking in your .m2 folder.


java_home   C:\Program Files\Java\jdk-17   environmnet variable
