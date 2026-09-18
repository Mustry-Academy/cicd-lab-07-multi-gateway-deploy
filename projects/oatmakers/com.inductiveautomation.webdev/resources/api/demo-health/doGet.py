def doGet(request, session):
	result = application.demo.health()
	response = request['servletResponse']
	response.setStatus(200 if result.get('ok') else 503)
	response.setContentType('application/json; charset=UTF-8')
	response.setHeader('Cache-Control', 'no-store')
	response.getWriter().print(system.util.jsonEncode(result))
	return None
