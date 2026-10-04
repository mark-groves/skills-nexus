Sidebar.prototype.addGCP2Palette = function() {
	this.addGCP2GeneralIconsPalette();
	this.addGCP2IconsComputePalette();
};

Sidebar.prototype.addGCP2GeneralIconsPalette = function() {
	var s = 1;
	var n = 'sketch=0;html=1;aspect=fixed;shape=mxgraph.gcp2.';
	this.createVertexTemplateEntry(n + 'clock',
		s * 100, s * 100, null, 'Clock', null, null, '');
	this.createVertexTemplateEntry(n + 'biomedical_trio',
		s * 100, s * 68, null, 'Biomedical Trio', null, null, '');
};

Sidebar.prototype.addGCP2IconsComputePalette = function() {
	var s = 200;
	var n = 'image=data:image/svg+xml,';
	this.createVertexTemplateEntry(n + 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjwvc3ZnPg==;',
		s * 0.19, s * 0.2, '', 'AI Hub', null, null, '');
};
