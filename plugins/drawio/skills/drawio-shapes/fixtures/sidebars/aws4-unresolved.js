Sidebar.prototype.addAWS4Palette = function() {
	this.addAWS4ComputePalette();
};

Sidebar.prototype.addAWS4ComputePalette = function() {
	var n = 'sketch=0;outlineConnect=0;shape=';
	this.createVertexTemplateEntry(n + 'mxgraph.aws4.ec2;',
		78, 78, '', 'EC2', null, null, null);
	this.createVertexTemplateEntry(svc('#ED7100') + 'retired_service;',
		78, 78, '', 'Retired Service', null, null, null);
};
