Sidebar.prototype.addGCPIconsPalette = function() {
	this.addGCPIconsGeneralPalette();
};

Sidebar.prototype.addGCPIconsGeneralPalette = function() {
	var n = 'image=data:image/svg+xml,';
	this.createVertexTemplateEntry(
		n + 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjwvc3ZnPg==;',
		s * 0.2, s * 0.2, '', 'Generic');
};
