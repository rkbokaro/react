Working- d-code-tpc and d-satsreact  for track diagram

			 HttpURLConnection conn = (HttpURLConnection) url
							.openConnection();   ---> this code for deployment

						HttpURLConnection conn = (HttpURLConnection)url.openConnection( new
					     Proxy(Proxy.Type.HTTP, new InetSocketAddress("172.16.1.61", 8080)) ); this code for developemnt
