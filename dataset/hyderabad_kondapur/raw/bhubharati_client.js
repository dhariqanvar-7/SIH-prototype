/**
 *  This program is having map controls
 */

var INCHES_PER_UNIT = {
	'm' : 39.37,
	'degrees' : 4374754
};
var DOTS_PER_INCH = 72;
var supportsFiltering = true;
var drawnFeatures = [];
var extentInfo = [];
var findInteraction;
var csvFeatures;
ILFSMargins = {
	applyMargins : function() {
		var leftToggler = $(".mini-submenu-left");
		var rightToggler = $(".mini-submenu-right");

		if (leftToggler.is(":visible")) {
			$("#map .ol-zoom").css("margin-left", 0).removeClass(
					"zoom-top-opened-sidebar").addClass("zoom-top-collapsed");
		} else {
			$("#map .ol-zoom").css("margin-left", $(".sidebar-left").width())
					.removeClass("zoom-top-opened-sidebar").removeClass(
							"zoom-top-collapsed");
		}
		if (rightToggler.is(":visible")) {
			$("#map .ol-rotate").css("margin-right", 0).removeClass(
					"zoom-top-opened-sidebar").addClass("zoom-top-collapsed");
		} else {
			$("#map .ol-rotate").css("margin-right",
					$(".sidebar-right").width()).removeClass(
					"zoom-top-opened-sidebar")
					.removeClass("zoom-top-collapsed");
		}
	},

	isConstrained : function() {
		return $("div.mid").width() == $(window).width();
	},

	applyInitialUIState : function() {
		if (ILFSMargins.isConstrained()) {
			$(".sidebar-left .sidebar-body").fadeOut('slide');
			$(".sidebar-right .sidebar-body").fadeOut('slide');
			$('.mini-submenu-left').fadeIn();
			$('.mini-submenu-right').fadeIn();
		}
	},

	sideMenuButton : function() {
		$('.sidebar-left .slide-submenu').on('click', function() {
			var thisEl = $(this);
			thisEl.closest('.sidebar-body').fadeOut('slide', function() {
				$('.mini-submenu-left').fadeIn();
				ILFSMargins.applyMargins();
			});
		});

		$('.mini-submenu-left').on('click', function() {
			var thisEl = $(this);
			$('.sidebar-left .sidebar-body').toggle('slide');
			thisEl.hide();
			ILFSMargins.applyMargins();
		});

		$('.sidebar-right .slide-submenu').on('click', function() {
			var thisEl = $(this);
			thisEl.closest('.sidebar-body').fadeOut('slide', function() {
				$('.mini-submenu-right').fadeIn();
				ILFSMargins.applyMargins();
			});
		});

		$('.mini-submenu-right').on('click', function() {
			var thisEl = $(this);
			$('.sidebar-right .sidebar-body').toggle('slide');
			thisEl.hide();
			ILFSMargins.applyMargins();
		});
	}
}

var ILFS = {
		
	loadDistricts: function (){
		var loadDistrict = $.ajax({
			type: "POST",
			url : "api/gis/district/",			
			success : function(data) {
				var slctSubcat=$('#district_id'), option="";
	            slctSubcat.empty();
	            
	            var tm_s = $('#tmField').val();
	            if(tm_s === 'true') {
	            	$('#district_id').attr("disabled", true);
	            }	            
	            option = option + '<option value="0">'+selectDistrict+'</option>';
	            for(var i=0; i<data.length; i++){
	                option = option + "<option value='"+data[i].district_id + "'>" + data[i].district_name_en + " | " + data[i].district_name_ll + "</option>";	                
	            }	            
	            slctSubcat.append(option);	            
	            var d = $("#districtField").val();
	            if (d) {
	            	 $("#district_id").val(d).change();
	            }	            
			},
			error : function(jqXHR, textStatus, errorThrown) {
				console.log(jqXHR.responseJSON.error);
			}
		});
	},
	
	loadDivisions : function(){
		ILFS.clearSelection();	
		$("#survey_id").val('');
		var disId = $("#district_id").val();
		var divId = $("#division_id").val();
		var formData = {};		
    	formData = {
    		district_id : disId,
    		division_id : divId
    	};
		var loadDivisions = $.ajax({
			type: "POST",
			contentType : "application/json",
			url : "api/gis/division/",
			data : JSON.stringify(formData),
			dataType : 'json',
			async : false,
			success : function(data) {
				var slctSubcat=$('#division_id'), option="";
				var slctSubcat_mandal=$('#mandal_id'), option_mandal="";
				var slctSubcat_vill=$('#village_id'), option_vill="";
	            slctSubcat.empty();
	            slctSubcat_mandal.empty();
	            slctSubcat_vill.empty();
	            var tm_s = $('#tmField').val();
	            if(tm_s === 'true') {
	            	$('#division_id').attr("disabled", true);
	            }
	            option = option + '<option value="0">'+selectDivision+'</option>';
	            option_mandal = option_mandal + '<option value="0">'+selectMandal+'</option>';
	            option_vill = option_vill + '<option value="0">'+selectVillage+'</option>';
	            for(var i=0; i<data.length; i++){
	                option = option + "<option value='"+data[i].division_id + "'>"+data[i].division_name_en+" | "+data[i].division_name_ll+"</option>";
	            }
	            slctSubcat.append(option);
	            slctSubcat_mandal.append(option_mandal);
	            slctSubcat_vill.append(option_vill);
	            vectorSource_search.clear();
	            map.removeLayer(edit_layers);
	            var d = $("#divisionField").val();
	            if (d) {
	            	 $("#division_id").val(d).change();
	            }
			},
			error : function(jqXHR, textStatus, errorThrown) {
				console.log(jqXHR.responseJSON.error);
			}
		});
	},
	
	loadMandals : function(){
		ILFS.clearSelection();	
		$("#survey_id").val('');
		var disId = $("#district_id").val();
		var divId = $("#division_id").val();
		var formData = {};		
    	formData = {
    		district_id : disId,
    		division_id : divId
    	};		
		var loadMandal = $.ajax({
			type : "POST",
			contentType : "application/json",
			url : "api/gis/mandal",
			data : JSON.stringify(formData),
			dataType : 'json',
			async : false,
			success : function(data) {
				var slctSubcat=$('#mandal_id'), option="";
				var slctSubcat_vill=$('#village_id'), option_vill="";
	            slctSubcat.empty();
	            slctSubcat_vill.empty();
	            var tm_s = $('#tmField').val();
	            if(tm_s === 'true') {
	            	$('#mandal_id').attr("disabled", true);
	            }
	            option = option + '<option value="0">'+selectMandal+'</option>';
	            option_vill = option_vill + '<option value="0">'+selectVillage+'</option>';
	            for(var i=0; i<data.length; i++){
	                option = option + "<option value='"+data[i].mandal_id + "'>"+data[i].mandal_name_en + " | "+data[i].mandal_name_ll + "</option>";
	            }
	            slctSubcat.append(option);
	            slctSubcat_vill.append(option_vill);
	            vectorSource_search.clear();	            
	            map.removeLayer(edit_layers);
	            var d = $("#mandalField").val();
	            if (d) {
	            	 $("#mandal_id").val(d).change();
	            }
			},
			error : function(jqXHR, textStatus, errorThrown) {
				console.log(jqXHR.responseJSON.error);
			}
		});
	},
	
	loadVillages : function(){	
		ILFS.clearSelection();	
		$("#survey_id").val('');
		var disId = $("#district_id").val();
		var divId = $("#division_id").val();
		var mandalId = $("#mandal_id").val();		
		var formData = {};		
    	formData = {
    		district_id : disId,
    		division_id : divId,
    		mandal_id : mandalId
    	};		
		var loadVillages = $.ajax({
			type : "POST",
			contentType : "application/json",
			url : "api/gis/village",
			data : JSON.stringify(formData),
			dataType : 'json',
			async : false,
			success : function(data) {
				var slctSubcat=$('#village_id'), option="";
	            slctSubcat.empty();
	            var tm_s = $('#tmField').val();
	            if(tm_s === 'true') {
	            	$('#village_id').attr("disabled", true);
	            }
	            option = option + '<option value="0">'+selectVillage+'</option>';
	            for(var i=0; i<data.length; i++) {
	                option = option + "<option value='"+data[i].village_id + "'>"+data[i].village_name_en + " | "+data[i].village_name_ll + "</option>";
	            }
	            slctSubcat.append(option);
	            vectorSource_search.clear();
	            map.removeLayer(edit_layers);
	            var d = $("#villageField").val();
	            if (d) {
	            	 $("#village_id").val(d);	            	 
	            	 ILFS.loadVillageMap('fromLangChange');
	            }
			},
			error : function(jqXHR, textStatus, errorThrown) {
				console.log(jqXHR.responseJSON.error);
			}
		});
	},
	
	loadVillageMap : function(comboVal){
		$("#survey_id").val('');
		var villageId = $("#village_id").val();
		if(comboVal == "fromLangChange") {
			var surveyNo = $("#surveyNoField").val();
		} else {
			var surveyNo = "";
		}
		
		vectorSource_search.clear();
		
		if($('#location').length > 0){
			$("#info_message").show();
			document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage" />';
			$("#location").empty();
		}		
		if(villageId != 0){		
			console.log(villageId);	
			map.removeLayer(edit_layers);
			map.addLayer(edit_layers);
			ILFS.init(villageId, surveyNo);
		}else if(villageId == 'null'){		
			ILFS.clearSelection();	
			$("#survey_id").val('');
			vectorSource_search.clear();
			map.removeLayer(edit_layers);
		}else{
			ILFS.clearSelection();	
			$("#survey_id").val('');
			vectorSource_search.clear();
			map.removeLayer(edit_layers);
		}		
	},
		
	getVillageExtent : function(vid, sno) {
		//debugger;
		var formData = {};		
    	formData = {
    		villageCode : vid,
    		surveyNumber :  sno
    	};
		var villageExtent = $.ajax({
			type : "POST",
			contentType : "application/json",
			url : "api/gis/bbox",
			data : JSON.stringify(formData),
			dataType : 'json',
			async : false,
			success : function(result) {
				if(result){
					//OK
					//alert('Extent Response ' + result[0].data);
				}				
			},
			error : function(jqXHR, textStatus, errorThrown) {
				//console.log("ERROR: ", jqXHR.responseJSON.error);
				alertMessage(7423452055, alert_vdna);
			}
		}).responseJSON;
		return (villageExtent.length!=0) ? villageExtent[0].data : null;
	},
	
	getVillageInfo : function(vid, sno, flag) {
		var formData = {};		
    	formData = {
    		villageCode : vid,
    		surveyNumber :  sno,
    		mapEditorFlag : flag
    	};
		var surveyNoInfo_View = $.ajax({
			type : "POST",
			contentType : "application/json",
			url : "api/gis/surveyinfo",
			data : JSON.stringify(formData),
			dataType : 'json',
			async : false,
			success : function(result) {
				if(result){
					//console.log(result);
					//alert('At Survey Info Response ' + result);
				}
			},
			error : function(jqXHR, textStatus, errorThrown) {
				//bootbox.alert(jqXHR.status);
				console.log("ERROR: ", jqXHR.responseText);
			}
		}).responseJSON;
    	return surveyNoInfo_View;
	},
	
	getSurveyMapById : function (){
		var villageId = $("#village_id").val();
		var surveyId = $("#survey_id").val();	
		
		if(villageId == "" || villageId ==  0){			
			alertMessage(9654224670, alert_vmnl);
			return false;
		}	
		
		if($('#tmField').val() != 'true') {          	 
			$("#surveyNoField").val(surveyId);
        }		 
		
		if(surveyId){
			$("#info_message").show();
			document.getElementById('info_message').innerHTML = "<p><i class='fa fa-spin fa-spinner'></i> Loading...please wait...</p>";
			ILFS.getSurveyMap(villageId, surveyId);
		}	
	},
	
	getSurveyMap : function(villageId, surveyId){
		if(villageId == "" || villageId ==  0){			
			alertMessage(9654224670, alert_vmnl);
			return false;
		} else {
			if(extent == null)
				{
				alertMessage(965422467087654, alert_vdna);
				return false;
				}else{
					$("#info_message").show();
					document.getElementById('info_message').innerHTML = "<p><i class='fa fa-spin fa-spinner'></i> Loading...please wait...</p>";
					var formData = {};			
			    	formData = {
			    		villageCode : villageId,
			    		surveyNumber :  surveyId
			    	};
					var surveyMap = $.ajax({
						type : "POST",
						contentType : "application/json",
						url : "api/gis/getsurveyidfeature",
						data : JSON.stringify(formData),
						dataType : 'json',
						async : false,
						success : function(result) {
							if(result){
								//console.log(result);
								//bootbox.alert('At Survey Info Response ' + result);
							}
						},
						error : function(jqXHR, textStatus, errorThrown) {
							//bootbox.alert(jqXHR.status + ' ' + jqXHR.responseText);
							console.log("ERROR: ", jqXHR.responseText);
						}
					}).responseJSON;
				}		
		}
		if(surveyMap == undefined || surveyMap == "undefined"){
			alertMessage(4123456798760988, "Something Went Wrong");	
			return false;
		}
		var feat = JSON.parse(surveyMap[0].feat_json.value);		
		if(feat.features != null){
			ILFS.displayAttributeInfo(feat, villageId, surveyId);
		} else {
			$("#survey_id").val('');
			if(surveyId != null || surveyId != undefined) {
				alertMessage(412345679876, alert_snne + " - " + surveyId);				
				ILFS.clearSelection();
				//$("#info_message").show();
	    	    //$("#location").empty();
	    	    document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage"/>';
	    	    $("#survey_id").val('');
			} else {
				alertMessage(0987654234, alert_ndas);				
				ILFS.clearSelection();
				//$("#info_message").show();
	    	   // $("#location").empty();
	    	    document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage"/>';
	    	    $("#survey_id").val('');
			}
			document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage"/>';
			$("#survey_id").val('');
		}				
		return null;
	},

	highlightStyle : new ol.style.Style({
          stroke: new ol.style.Stroke({
            color: '#f00',
            width: 1
          }),
          fill: new ol.style.Fill({
            color: 'rgba(255,0,0,0.1)'
          }),
          text: new ol.style.Text({
            font: '14px Calibri,sans-serif',
            fill: new ol.style.Fill({
              color: '#000000'
            }),
            stroke: new ol.style.Stroke({
              color: '#FFFF99',
              width: 3.5
            })
          })
        }),
    
	 FMEStyle: (function() {
        var style = new ol.style.Style({
          stroke: new ol.style.Stroke({
            color: '#f00',
            width: 1
          }),
          /*fill: new ol.style.Fill({
            color: 'rgba(255,0,0,0.1)'
          }),*/
          text: new ol.style.Text({
            text: 'area',
            scale: 1.3,
            font: '12px Calibri,sans-serif',
            fill: new ol.style.Fill({
              color: '#000000'
            })
            /*stroke: new ol.style.Stroke({
              color: '#FFFF99',
              width: 3.0
            })*/
          })
        });
        var styles = [style];
        return function(feature, resolution) {
          style.getText().setText(feature.get("area"));
          return styles;
        };
      })(),

	init : function(villageId, survey_number) {
		if(survey_number){
			//OK
		} else {
			survey_number = null;
		}
		kid_search = document.getElementById("searchkid").value;
		surveyNo = (kid_search != '') ? kid_search : survey_number;	
		
		if(kid_search == "" || kid_search == null){
			filter = "village_id='"+villageId+"'";
		} else {
			filter = "village_id='"+villageId+"' AND survey_number='" + surveyNo + "'";
		}		
		extent = ILFS.getVillageExtent(villageId, surveyNo);
		//console.log(extent);
		
		var filterParams = {'CQL_FILTER': null };
        if (filter.replace(/^\s\s*/, '').replace(/\s\s*$/, '') != "") {         
            filterParams["CQL_FILTER"] = filter;               
        }
        wmsLayer.setSource(wmsSource);
		wmsLayer.getSource().updateParams(filterParams);
		
		if(extent != undefined){
			map.getView().fit(extent, map.getSize());
			if(survey_number != null){
				ILFS.getSurveyMap(villageId, survey_number);
			}
		}else {
			alertMessage(4198765, alert_vdna);
		}
	},	
	
	detectmob : function () {
 	   if(window.innerWidth <= 593) {
 	     return true;
 	   } else {
 	     return false;
 	   }
 	},
	
	displayAttributeInfo : function (myJson, villageId, surveyId){
							        	   
		var format = new ol.format.GeoJSON();
		var feature = format.readFeatures(myJson);
		csvFeatures = feature[0].getGeometry().getCoordinates();
		vectorSource_search.clear();
		vectorSource_search.addFeatures(feature);		
		vectorLayer_search.setStyle(ILFS.highlightStyle);
		map.getView().fit(vectorLayer_search.getSource().getExtent(), map.getSize());
		/*vectorLayer_search.once('render', function() {
	         map.getView().fit(vectorLayer_search.getSource().getExtent(), map.getSize());
	         map.getView().setZoom(map.getView().getZoom()-1);	        
	    });*/
		
		var sInfo = ILFS.getVillageInfo(villageId, surveyId, displayPahaniDetails);
		//console.log(sInfo);
		var baseSyrveyNumber = null;
		if(sInfo.data.length != 0) {			
			if(sInfo.data.length === 1){
				baseSyrveyNumber = sInfo.data[0].survey_number;
			} else {
				baseSyrveyNumber = sInfo.data[0].base_survey_no;
			}
		}
		if(sInfo.data.length === 0 || sInfo.total_land_extent.length === 0){			
			alertMessage(234321112, alert_ndas + " - <b>" + surveyId);	
			$("#info_message").hide();
    	    $("#location").empty();
			//$("#info_message").show();
			document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage" />';			
		} else {
			$("#info_message").hide();
    	    $("#location").empty();
    	    
    	    // Hide other accordions
    	    var isvillageInfoDivVisible = $("#villageInfoDiv").attr("aria-expanded");
    	    var isLayerPanelVisible = $("#layerInfoDiv").attr("aria-expanded");
    	    var isParcelPanelVisible = $("#parcelInfoDiv").attr("aria-expanded");
    	    
    	    if(typeof isvillageInfoDivVisible == 'undefined' || isvillageInfoDivVisible == "true") {
    	    	$("#villageInfoDiv").click();
    	    }
    	    
    	    if(typeof isLayerPanelVisible == 'undefined' || isLayerPanelVisible == "true") {
    	    	$("#layerInfoDiv").click();
    	    }
    	    
    	    if(isParcelPanelVisible == "false") {
    	    	$("#parcelInfoDiv").click();
    	    }
    	    
    	    var trHTML = '';					
    	    trHTML += '<table lang="te" id="location" class="table table-sm table-small-font table-striped table-hover">';
    	    if(rsrextent === true){
    	    	trHTML += '<tr><td>సర్వే సంఖ్య </td><td colspan="3">మొత్తం RSR విస్తీర్ణం</td></tr>';
        	    trHTML += '<tr><td>'+sInfo.total_rsr_extent[0].surveyno+'</td><td colspan="3">'+sInfo.total_rsr_extent[0].rsrextent+'</td></tr>';
    	    }	        
    	    trHTML += '<tr><td>సర్వే సంఖ్య </td><td colspan="3">మొత్తం  విస్తీర్ణం</td></tr>';
    	   // trHTML += '<tr><td>'+baseSyrveyNumber+'</td><td>'+sInfo.total_land_extent[0].total_extent+'</td><td><img style="width: 15px;" class="img-responsive" src="./img/tippon_view.png" id="viewtippon" onclick="ILFS.viewTipponDocument();" data-toggle="tooltip" title="View Tippon"/></td><td><img style="width: 15px;" class="img-responsive" src="./img/ecview.png" id="viewEC" data-toggle="tooltip" title="View EC" onclick="ILFS.publicViewEC('+"'" + baseSyrveyNumber + "'"+')"/></td></tr>';
    	    trHTML += '<tr><td>'+baseSyrveyNumber+'</td><td>'+sInfo.total_land_extent[0].total_extent+'</td><td><img style="width: 15px;" class="img-responsive" src="./img/tippon_view.png" id="viewtippon" onclick="ILFS.viewTipponDocument();" data-toggle="tooltip" title="View Tippon"/></td></tr>';
    	    trHTML += '<tr><td>సర్వే సంఖ్య / ఉప విభాగం </td><td colspan="3">విస్తీర్ణం </td></tr>';
	        $.each(sInfo.data, function (i, item) {
	        	if(displayPahaniDetails === false){
	        		trHTML += '<tr>';
	        	} else {
	        		trHTML += '<tr class="clickable" data-toggle="collapse" data-target="#expandSInfo'+[i]+'" >';
	        	}	        	
	        	trHTML += '<td>' + sInfo.data[i].survey_number + '</td>';
	        	trHTML += '<td colspan="3">' + sInfo.data[i].total_extent_of_land + '</td>';
	        	//trHTML += '<td><i class="fa fa-plus text-success" style="color:blue"></i></td>';
	        	if(displayPahaniDetails === false){
	        		//trHTML += '<td colspan="1"><img style="width: 15px;" class="img-responsive" src="./img/view.png" id="viewPahani" data-toggle="tooltip" title="View Pahani" onclick="ILFS.publicViewPahani('+"'" + sInfo.data[i].khata_number + "'"+', '+"'" + sInfo.data[i].survey_number + "'"+')"/></td><td><img style="width: 15px;" class="img-responsive" src="./img/ecview.png" id="viewEC" data-toggle="tooltip" title="View EC" onclick="ILFS.publicViewEC('+"'" + sInfo.data[i].survey_number + "'"+')"/></td>';
	        		//trHTML += '<td><img style="width: 15px;" class="img-responsive" src="./img/ecview.png" id="viewEC" data-toggle="tooltip" title="View EC" onclick="ILFS.publicViewEC('+"'" + sInfo.data[i].survey_number + "'"+')"/></td>';
	        	} else {
	        		//trHTML += '<td><img class="img-responsive" src="./img/view.png" id="viewPahani" data-toggle="tooltip" title="View Pahani" onclick="ILFS.publicViewPahani('+"'" + sInfo.data[i].khata_number + "'"+', '+"'" + sInfo.data[i].survey_number + "'"+')"/> &nbsp;&nbsp; <a data-toggle="collapse" data-target="#expandSInfo'+[i]+'" aria-expanded="false" aria-controls="menu"> <i class="fa fa-plus" style="color:blue"></i><i class="fa fa-minus" style="color:red"></i></a></td>';
	        		//trHTML += '<td><img style="width: 15px;" class="img-responsive" src="./img/ecview.png" id="viewEC" data-toggle="tooltip" title="View EC" onclick="ILFS.publicViewEC('+"'" + sInfo.data[i].survey_number + "'"+')"/> &nbsp;&nbsp; <a data-toggle="collapse" data-target="#expandSInfo'+[i]+'" aria-expanded="false" aria-controls="menu"> <i class="fa fa-plus" style="color:blue"></i><i class="fa fa-minus" style="color:red"></i></a></td>';
	        	}	        	
	        	trHTML += '</tr>';
	   		        	
	        	trHTML += '<tr id="expandSInfo'+[i]+'" class="panel-collapse collapse out"><td width="100%" colspan="3">';
	        	trHTML += '<table class="table table-striped table-hover table-bordered table-dark tablebgcolor "><tr><td>పట్టాదారు పేరు </td>';
	        	trHTML += '<td>' + sInfo.data[i].pattadar_name + '</td></tr>'
	        	trHTML += '<tr><td>పట్టాదారు తండ్రి పేరు </td><td>' + sInfo.data[i].pattadat_father_name + '</td></tr>';
	        	trHTML += '<tr><td>అనుభవదారు పేరు  </td><td>' + sInfo.data[i].occupant_name + '</td></tr>';
	        	trHTML += '<tr><td>అనుభవదారు తండ్రి / భర్త  పేరు  </td><td>' + sInfo.data[i].occupant_father_name + '</td></tr>';
	        	trHTML += '<tr><td>అనుభవ విస్తీర్ణం  </td><td>' + sInfo.data[i].occupant_extent + '</td></tr>';
	        	trHTML += '<tr><td>సాగుకు పనికి వచ్చు విస్తీర్ణం </td><td>' + sInfo.data[i].cultiable_land + '</td></tr>';
	        	trHTML += '<tr><td>సాగుకు పనికి రాని విస్తీర్ణం </td><td>' + sInfo.data[i].uncultivated_land + '</td></tr>';
	        	trHTML += '<tr><td>భూమి స్వభావం </td><td>' + sInfo.data[i].land_nature_ll + '</td></tr>';
	        	trHTML += '<tr><td>భూమి వివరణ </td><td>' + sInfo.data[i].land_classification_ll + '</td></tr>';
	        	trHTML += '<tr><td>వ్యవసాయ విస్తరణ </td><td>' + sInfo.data[i].agri_extents + '</td></tr>';
	        	trHTML += '<tr><td>వ్యవసాయేతర విస్తరణ </td><td>' + sInfo.data[i].nonagri_extents + '</td></tr>';
	        	trHTML += '</table></td></tr>';			        	
	        	
	        });		        
	        $('#location').append(trHTML);
	        
	       /* if(ILFS.detectmob()){
	        	bootbox.alert({ 
	  	  		  size: "small",
	  	  		  message: trHTML, 
	  	  		  callback: function(){  your callback code  }
	  	  		}).find('.modal-content').css({'font-size': '0.76555em', 'opacity': '0.75'} );
	        }	 */       
    	   
	        $('.fa-plus').on('click', function(){
	        	$(this).parent().find(".fa-plus").removeClass("fa-plus").addClass("fa-minus");
	        }).on('click', function(){
	        	$(this).parent().find(".fa-minus").removeClass("fa-minus").addClass("fa-plus");
	        });	
        
		}
	},
	
	publicViewPahani: function(khataNo, survNo){
   	 //debugger;
   	 	var villageId = $("#village_id").val();   	 	
   	 	var district = $("#district_id").val();
		var mandal = $("#mandal_id").val();   	 
        var khata_id = khataNo;
        //var survey_id=document.getElementById("surveyIdselect").value;
        var survey_id = survNo;
        
        if(khata_id!='0'){
       	 	document.getElementById("khataNumberPdf").value=khata_id; 
        } else {
       	 	document.getElementById("khataNumberPdf").value=survey_id;
        }
        document.getElementById("villageIdPdf").value=villageId;
        
        var village = document.getElementById("village_id");
        var villageNameLL=village.options[village.selectedIndex].text.split("|")[1];
        document.getElementById("villageLl").value=villageNameLL.trim();
                                 
        var district = document.getElementById("district_id");
        var districtNameLL=district.options[district.selectedIndex].text.split("|")[1];
        document.getElementById("districtLl").value=districtNameLL.trim();
        
        var mandal = document.getElementById("mandal_id");
        var mandalNameLL=mandal.options[mandal.selectedIndex].text.split("|")[1];
        document.getElementById("mandalLl").value=mandalNameLL.trim();      
   	 
   	 	document.getElementById("surveyNumberPdf").value = survNo;
		/*document.requestForm.action = "http://125.19.63.165:9086/dharani/viewPahani";*/   	 	
		document.requestForm.action = pahaniCopy;
		document.requestForm.target = "_blank";
	    document.requestForm.submit();		
	},	
	
	interaction : new ol.interaction.DragBox({
		condition : ol.events.condition.noModifierKeys,
		style : new ol.style.Style({
			stroke : new ol.style.Stroke({
				color : [ 255, 0, 0, 4 ]
			})
		})
	}),
	
	getCurrentInteraction : function () {
		map.getInteractions().forEach(function (interaction) {
		   if (interaction instanceof ol.interaction.DragBox) {
			   findInteraction=interaction;
		   } /*else if (interaction instanceof ol.interaction.DragPan) {
			   findInteraction=interaction;
		   }*/ else if (interaction instanceof ol.interaction.Draw) {
			   findInteraction=interaction;
		   } else if (interaction instanceof ol.interaction.Select) {
			   findInteraction=interaction;
		   } else if (interaction instanceof ol.interaction.Modify) {
			   findInteraction=interaction;
		   } 
		});
		return findInteraction;
	},

	getDrawInteraction : function(type, source) {
		interaction = new ol.interaction.Draw({
			type : type,
			source : source
		})
		return interaction;
	},

	getZoomIn : function(map) {
		map.removeInteraction(ILFS.interaction);
		if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		ILFS.interaction.on('boxend', function(evt) {
			var extent = evt.target.getGeometry().getExtent();
			map.getView().fit(extent, map.getSize());
		});
		map.addInteraction(ILFS.interaction);
	},

	getZoomOut : function(map) {
		//map.removeInteraction(ILFS.interaction);
		if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		ILFS.interaction.on('boxend', function(evt) {
			var currentZoom = map.getView().getZoom();
			map.getView().setZoom(currentZoom - 1);
		});
		map.addInteraction(ILFS.interaction);
	},

	getMapPan : function() {
		map.removeInteraction(ILFS.interaction);
		//if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		var interaction = new ol.interaction.DragPan();
		map.on('pointerdrag', function(evt) {
			map.getViewport().style.cursor = "-webkit-grabbing";
		});
		map.on('pointerup', function(evt) {
			map.getViewport().style.cursor = "-webkit-grab";
		});
		map.addInteraction(interaction);
	},

	drawPoint : function() {
		map.removeInteraction(ILFS.interaction);
		interaction = ILFS
				.getDrawInteraction('Point', drawingLayer.getSource());
		interaction.on('drawend', function(e) {
			var feature = e.feature;
			/*
			 * drawnFeatures.push(feature); feature.setProperties({ 'id' :
			 * ILFS.setFeatureIDtoDrawnLayer(feature) });
			 * ILFS.addDrawnFeature(feature);
			 * 
			 * var sourceLayer2 = drawingLayer.getSource(); var features2 =
			 * sourceLayer2.getFeatures(); console.log(features2);
			 */
			map.removeInteraction(interaction);
		});
		map.addInteraction(interaction);
	},

	drawLine : function() {
		map.removeInteraction(ILFS.interaction);
		interaction = ILFS.getDrawInteraction('LineString', drawingLayer
				.getSource());
		interaction.on('drawend', function(e) {
			var feature = e.feature;
			/*
			 * drawnFeatures.push(feature); feature.setProperties({ 'id' :
			 * ILFS.setFeatureIDtoDrawnLayer(feature) });
			 * ILFS.addDrawnFeature(feature);
			 * 
			 * var sourceLayer2 = drawingLayer.getSource(); var features2 =
			 * sourceLayer2.getFeatures(); console.log(features2);
			 */
			map.removeInteraction(interaction);
		});
		map.addInteraction(interaction);
	},

	drawPolygon : function() {
		map.removeInteraction(ILFS.interaction);
		interaction = ILFS.getDrawInteraction('Polygon', drawingLayer
				.getSource());
		interaction.on('drawend', function(e) {
			var feature = e.feature;
			drawnFeatures.push(feature);
			feature.setProperties({
				'id' : ILFS.setFeatureIDtoDrawnLayer(feature)
			});
			ILFS.addDrawnFeature(feature);

			var sourceLayer2 = drawingLayer.getSource();
			var features2 = sourceLayer2.getFeatures();
			console.log(features2);
			map.removeInteraction(interaction);
		});
		map.addInteraction(interaction);
	},

	setFeatureIDtoDrawnLayer : function(features) {
		var sourceLayer = drawingLayer.getSource();
		var features = sourceLayer.getFeatures();

		if (features.length == 0) {
			featureID = featureID + 1;
		} else {
			featureID = features.length + 1;
		}

		/*
		 * features.setProperties({ 'id' : featureID });
		 */

		//console.log(featureID);
		return featureID;
	},

	addDrawnFeature : function(e) {
		drawingLayer.getSource().on('addfeature', function(e) {
			var index = drawnFeatures.indexOf(e.feature);
			if (index > -1) {
				// feature added to source from drawinteraction
				drawnFeatures.splice(index, 1);
			}
		})
		return null;
	},

	selectFeature : function() {
		map.removeInteraction(interaction);
		interaction = new ol.interaction.Select({
			condition : ol.events.condition.click,
			layers : [ drawingLayer ]
		});
		interaction.on('select', function(event) {
			alert();
			selectedFeature = event.selected[0];
		});
		map.addInteraction(interaction);
	},

	modifyFeature : function() {
		map.removeInteraction(ILFS.interaction);
		interaction = new ol.interaction.Modify(
				{
					features : new ol.Collection(drawingLayer.getSource()
							.getFeatures()),
					deleteCondition : function(event) {
						return ol.events.condition.shiftKeyOnly(event)
								&& ol.events.condition.singleClick(event);
					},
					save : ILFS.getJSONFeatures()
				});
		interaction.on('drawend', function(e) {
			var feature = e.feature;

			map.removeInteraction(interaction);
		});
		map.addInteraction(interaction);
	},

	getJSONFeatures : function() {
		var writer = new ol.format.GeoJSON();
		var geojsonStr = writer.writeFeatures(drawingLayer.getSource().getFeatures());
		// console.log(geojsonStr);
		return geojsonStr;
	},

	deleteFeature : function() {
		//debugger;
		document.getElementById('deleteFeature').addEventListener('click',
				function() {
					drawingLayer.getSource().removeFeature(selectedFeature);
				});
	},

	measureLength : function() {
		map.removeInteraction(ILFS.interaction);
		interaction = ILFS.getDrawInteraction('LineString', measureLayer
				.getSource());
		interaction.on('drawstart', function(e) {
			measureLayer.getSource().clear();
		});
		interaction.on('drawend', function(e) {
			var feature = e.feature;
			var distance = feature.getGeometry().getLength();
			var measureLength = distance > 100 ? (distance / 1000).toFixed(3)
					+ 'km' : distance.toFixed(3) + 'm';
			console.log(measureLength);
			document.getElementById("length").innerHTML = measureLength;
			map.removeInteraction(interaction);
		});
		map.addInteraction(interaction);
		map.removeLayer(measureLayer);
	},

	measureArea : function() {
		map.removeInteraction(ILFS.interaction);
		interaction = ILFS.getDrawInteraction('Polygon', measureLayer.getSource());
		map.addLayer(measureLayer);
		interaction.on('drawstart',	function(e) {
			measureLayer.getSource().clear();
			e.feature.on('change', function(event) {
				var feature = e.feature;
				var area = feature.getGeometry().getArea();
				bootbox.alert("Measure Area <br>", function (){(area / 4046.85642).toFixed(4) + "  ఎ.గుo" });
				//document.getElementById("length").innerHTML = (area / 4046.85642).toFixed(4) + "  ఎ.గుo";
			});
		});
		interaction.on('drawend', function(e) {
			var feature = e.feature;
			map.removeInteraction(interaction);
		});
		map.addInteraction(interaction);
		map.removeLayer(measureLayer);
	},
	/*formatCoord : function(fraction) {
		  var template = '{y} | {x}';
		  return (
		    function(coordinate) {
		    	return ol.coordinate.format(coordinate, template, fraction);
		    });
		},*/
	mpControl : function(){
		var mousePositionControl = null;
		if(mousePositionControlFlag === true){
			mousePositionControl = new ol.control.MousePosition({
				target : document.getElementById('mouse-position'),
				coordinateFormat : function(coord) {
		              var latlong = ol.coordinate.toStringHDMS(coord, 3);
		              var lat = latlong.split("N");
		              var long = lat[1].split("E");
		              var displaycoords = lat[0] +"N,"+long[0]+"E";
		              return displaycoords;
		          },
					// ILFS.formatCoord(5),
				// coordinateFormat: createStringXY(4),
				projection: 'EPSG:4326',
				// comment the following two lines to have the mouse position be placed within the map.
				className : 'mouse-position',
				target : document.getElementById('mouse-position'),
				//undefinedHTML : '&nbsp;'
			})
		}
		return mousePositionControl;
	},

	parcelProjection : new ol.proj.Projection({
		code : 'EPSG:' + projectionval,
		units : 'm'
	}),
	
	getCenterOfExtent : function (Extent) {
		var X = eval(Extent[0]) + (eval(Extent[2]) - eval(Extent[0])) / 2;
		var Y = eval(Extent[1]) + (eval(Extent[3]) - eval(Extent[1])) / 2;
		return [ X, Y ];
	},

	getScaleFromMap : function(map) {
		map.getView().on('change:resolution', function(evt) {
			var resolution = evt.target.get('resolution');
			var units = map.getView().getProjection().getUnits();

			dpi = 25.4 / 0.28;
//			console.log('dpi', dpi);
			var scale = resolution * 39.37 * dpi;
			if (scale >= 9500 && scale <= 950000) {
				scale = Math.round(scale / 1000) + "K";
			} else if (scale >= 950000) {
				scale = Math.round(scale / 1000000) + "M";
			} else {
				scale = Math.round(scale);
			}
			document.getElementById('scale').value = "1 : " + scale;
		})
	},
	
	clearSelection : function(){		
		vectorSource_search.clear();
		if ($('#location').length)
	   	{
			$("#location").empty();
			$("#info_message").show();
			document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage" />';
	   	}		
		// Find the double click interaction that is on the map.
		// Remove the interaction from the map.
		map.removeInteraction(ILFS.interaction);
		if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		
	},
	
	displayTonchMap : function () {
		console.log("TonchMap Selected");		
		var village_id = $("#village_id").val();
		var surveyNo = $("#surveyNoField").val();
		if(village_id != 0 && surveyNo != "") {
			bootbox.prompt({
				/*size: "small",*/
			    title: "<span style='font-size: medium;'>Tonch Map Scale</span>",
			    inputType: 'select',
			    inputOptions: [	
			    	{
			            text: 'Select Scale....',
			            value:'',
			        },
			        {
			            text: '8" = 1 MILE',
			            value: '3960',
			        },
			        {
			            text: '16" = 1 MILE',
			            value: '7920',
			        }
			    ],			    
			    buttons: {
					cancel: {
						label: 'Cancel',
						className: 'btn-danger',
						callback: function () {
							bootbox.alert('Cancel Button Pressed');
							return false;
						}
					},
					confirm: {
						label: 'Get Tounch Map',
						className: 'btn-success',
						callback: function () {
							bootbox.alert('Save Button Pressed');
						}
					}
				},
			    callback: function (result) {
			        if (result != null) {
			        	console.log(result);
//				        ILFS.showPrintMap(village_id,surveyNo,result);
			        	 ILFS.showPrintPdfMap(village_id,surveyNo,result, parseInt(Math.ceil(dpi)));
		            } else {
		            	//bootbox.alert("Please select scale");
			            return false;
		            }
			    }
			}).find("div.modal-content").addClass("confirmWidth");	
			$('.modal-content').css('width','300px');
			let op = $('.bootbox-input').children()[0];
			op.hidden='true';
			op.selected='true';
			let hd = $('.modal-title span');
			hd.css({"font-size":"large","font-weight":"bold"});
		} else {
			alert("Please select village and parcel");
		}
	},
	
	showPrintMap : function (village_id,surveyNo,scale){
				
		if(scale != null){
			var jspcall = "printtonchmap?village_id="+village_id+"&survey_number="+surveyNo+"&scale="+scale;
		    window.open(jspcall, '_blank');	
		} else {
			var jspcall = "printtonchmap?village_id="+village_id+"&survey_number="+surveyNo;
		    window.open(jspcall, '_blank');	
		}
		console.log(village_id, surveyNo, scale);
	},
	
	loadDevice: function (){
		var loadDevicedata = $.ajax({
			type: "POST",
			contentType : "application/json",
			url : "getdevice",
			dataType : 'json',
			async : false,
			success : function(data) {
				if (data) {
					//console.log(data)
				}						
			},
			error : function(jqXHR, textStatus, errorThrown) {
				console.log(jqXHR.responseJSON.error);
			}
		}).responseJSON;
		return loadDevicedata;
	},	
	loadProjection: function (){
		var loadProjectionInfo = $.ajax({
			type: "POST",
			contentType : "application/json",
			url : "getProjection",
			dataType : 'json',
			async : false,
			success : function(data) {
				//console.log(data);				
			},
			error : function(jqXHR, textStatus, errorThrown) {
				console.log(jqXHR.responseJSON.error);
			}
		}).responseJSON;
		return loadProjectionInfo;
	},	
	fullzoom : function(map) {
		map.getView().fit(extent, map.getSize());
	},

	getScaleFromResolution : function(units, resolution) {
		var scale = INCHES_PER_UNIT[units] * DOTS_PER_INCH * resolution;
		scale = Math.round(scale);
		return ILFS.roundUp(scale);
	},

	roundUp : function(value) {
		return (~~((value + 99) / 100) * 100);
	},
	
	clearInteraction : function () {
		map.getInteractions().forEach(function (interaction) {
		   if (interaction instanceof ol.interaction.Draw) {
			   map.removeInteraction(interaction);
		   }
		   
		   if (interaction instanceof ol.interaction.DragPan) {
			   map.removeInteraction(interaction);
			   map.getViewport().style.cursor="";
		   }
		   
		   if (interaction instanceof ol.interaction.Snap) {
			   map.removeInteraction(interaction);
		   }
		});
		isSnappingActivated = false;
		closer.click();
		
		if(typeof geoRefPointSelect != "undefined") {
			geoRefPointSelect.getFeatures().clear();
		}
		
		if(typeof rotateFeatureSelect != "undefined") {
			rotateFeatureSelect.getFeatures().clear();
		}
		
		if(typeof LabelFeatureSelect != "undefined") {
			
			LabelFeatureSelect.getFeatures().clear();
			
			map.getInteractions().forEach(function (interaction) {
			   if (interaction instanceof ol.interaction.Select) {
				   map.removeInteraction(interaction);
			   }
			});
		}
		
		if(typeof hangingLineSelect != "undefined") {
			hangingLineSelect.getFeatures().clear();
			map.getInteractions().forEach(function (interaction) {
			   if (interaction instanceof ol.interaction.Select) {
				   map.removeInteraction(interaction);
			   }
			});
		}
		
		$("#otherLinesCombo").val("");
		$("#otherTextCombo").val("");
	},
	
	drawSurveyBaseLine : function() {
		addBaseLineDrawInteraction();
	},
	
	addSurveyDisOffset : function() {
		startDistanceOffsetInteraction();
	},
	
	drawSurveyPolygon : function() {
		ILFS.clearInteraction();
		drawSurveyPolygon();
	},
	
	selectSurveyPolygon : function() {
		selectToRotateFeature();
	},
	
	getSurveyMapZoomIn : function(map) {
		ILFS.clearInteraction();
		map.removeInteraction(ILFS.interaction);
		if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		ILFS.interaction.on('boxend', function(evt) {
			var extent = evt.target.getGeometry().getExtent();			
			map.getView().fit(extent, map.getSize());
		});
		map.addInteraction(ILFS.interaction);
	},

	getSurveyMapZoomOut : function(map) {
		ILFS.clearInteraction();
		//map.removeInteraction(ILFS.interaction);
		if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		ILFS.interaction.on('boxend', function(evt) {
			var currentZoom = map.getView().getZoom();
			map.getView().setZoom(currentZoom - 1);
		});
		map.addInteraction(ILFS.interaction);
	},

	getSurveyMapPan : function(map) {
		ILFS.clearInteraction();
		map.removeInteraction(ILFS.interaction);
		//if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		var interaction = new ol.interaction.DragPan();
		map.on('pointerdrag', function(evt) {
			map.getViewport().style.cursor = "-webkit-grabbing";
		});
		map.on('pointerup', function(evt) {
			map.getViewport().style.cursor = "-webkit-grab";
		});
		map.addInteraction(interaction);
	},
	getSateliteMapPan : function(map) {
		ILFS.clearInteraction();
		map.removeInteraction(ILFS.interaction);
		//if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		var interaction = new ol.interaction.DragPan();
		map.on('pointerdrag', function(evt) {
			map.getViewport().style.cursor = "-webkit-grabbing";
		});
		map.on('pointerup', function(evt) {
			map.getViewport().style.cursor = "-webkit-grab";
		});		
		map.addInteraction(interaction);
	},
	fullExtentSurveyMap : function(map,extent) {
		if(extent != undefined) {
			map.getView().fit(extent, map.getSize());
		}
	},
	
	clearSurveyMapSelection : function(map){
		ILFS.clearInteraction();
		vectorSource_search.clear();
		if ($('#location').length)
	   	{
			$("#location").empty();
			$("#info_message").show();
			document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage" />';
	   	}		
		// Find the double click interaction that is on the map.
		// Remove the interaction from the map.
		map.removeInteraction(ILFS.interaction);
		if (ILFS.getCurrentInteraction()) { map.removeInteraction(ILFS.getCurrentInteraction()); }
		
	},
	
	markInMap : function() {
		ILFS.clearInteraction();
		ILFS.unregisterEvents(satelliteMap);
		markInMap();
	},
	
	selectPointInPolygon : function() {
		selectPointInPolygon();
	},
	
	selectGeoRefPolygonToRotate : function() {
		ILFS.clearSatelliteMapInteraction();
		ILFS.unregisterEvents(satelliteMap);
		selectGeoRefPolygonToRotate();
	},
	
	selectGeoRefPointToMove : function() {
		ILFS.clearInteraction();
		ILFS.clearSatelliteMapInteraction();
		ILFS.unregisterEvents(satelliteMap);
		selectGeorefPolygonPointToMove();
	},
	
	clearAllLayersAndControls : function() {
		ILFS.clearInteraction();
		clearAllLayerFeatures();
	},
	
	unregisterEvents : function(map) {
		map.removeEventListener('click');
		map.removeEventListener('singleclick');
	},
	
	clearSatelliteMapInteraction : function() {
		satelliteMap.getInteractions().forEach(function (interaction) {
			   if (interaction instanceof ol.interaction.Draw) {
				   satelliteMap.removeInteraction(interaction);
			   }
			   
			   if (interaction instanceof ol.interaction.DragPan) {
				   satelliteMap.removeInteraction(interaction);
				   satelliteMap.getViewport().style.cursor="";
			   }
			   
			   if (interaction instanceof ol.interaction.Snap) {
				   satelliteMap.removeInteraction(interaction);
			   }
			});
		
			satOverlayCloser.click();
			
			if(typeof geoRefPointMoveSelect != "undefined") {
				geoRefPointMoveSelect.getFeatures().clear();
			}
			
			if(typeof geoRefRotateFeaturePointSelect != "undefined") {
				geoRefRotateFeaturePointSelect.getFeatures().clear();
			}
	},
	clearAllSurveyLayerFeatures : function() {
		ILFS.clearInteraction();
		clearAllSurveyLayerFeatures();
	},
	clearAllSatelliteLayerFeatures : function() {
		ILFS.clearInteraction();
		clearAllSatelliteLayerFeatures();
	},
	selectAnnotationLabel : function() {
		ILFS.clearInteraction();
		ILFS.unregisterEvents(map);
		selectAnnotationLabel();
	},
	showPolygonArea : function () {
		showPolygonArea();
	},
	showSatellitePolygonArea : function () {
		showSatellitePolygonArea();
	},	
	updateOffsetLine : function() {
		ILFS.clearInteraction();
		ILFS.unregisterEvents(map);
		updateOffsetLine();
	},
	deleteLines : function() {
		ILFS.clearInteraction();
		ILFS.unregisterEvents(map);
		deleteLines();
	},
	deletePolygon : function() {
		ILFS.clearInteraction();
		ILFS.unregisterEvents(map);
		deletePolygon();
	},
	deleteTexts : function() {
		ILFS.clearInteraction();
		ILFS.unregisterEvents(map);
		deleteTexts();
	},
	selectPolygonToSave : function() {
		ILFS.clearInteraction();
		ILFS.unregisterEvents(satelliteMap);
		selectPolygonToSave();
	},
	selectNonGeoCodePolygonToSave : function() {
		ILFS.clearInteraction();
		ILFS.unregisterEvents(map);
		selectNonGeoCodePolygonToSave();
	},
	fmbZoomIn : function(inMap) {
		
		SURVEYUTILS.unregisterMouseEvents(inMap,"singleclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"dblclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"pointermove");
		SURVEYUTILS.removeAllDrawInteractions(inMap);
		SURVEYUTILS.removeSelectInteractions(inMap);
		SURVEYUTILS.removeAllSnapInteractions(inMap);
		
		ILFS.interaction.on('boxend', function(evt) {
			var extent = evt.target.getGeometry().getExtent();
			inMap.getView().fit(extent, inMap.getSize());
		});
		inMap.addInteraction(ILFS.interaction);
	},
	fmbZoomOut : function(inMap) {
		SURVEYUTILS.unregisterMouseEvents(inMap,"singleclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"dblclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"pointermove");
		SURVEYUTILS.removeAllDrawInteractions(inMap);
		SURVEYUTILS.removeSelectInteractions(inMap);
		SURVEYUTILS.removeAllSnapInteractions(inMap);
		
		ILFS.interaction.on('boxend', function(evt) {
			var currentZoom = inMap.getView().getZoom();
			inMap.getView().setZoom(currentZoom - 1);
		});
		inMap.addInteraction(ILFS.interaction);
	},
	fmbMapPan : function(inMap) {
		SURVEYUTILS.unregisterMouseEvents(inMap,"singleclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"dblclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"pointermove");
		SURVEYUTILS.removeAllDrawInteractions(inMap);
		SURVEYUTILS.removeSelectInteractions(inMap);
		SURVEYUTILS.removeAllSnapInteractions(inMap);
		
		inMap.getInteractions().forEach(function (interaction) {
		   if (interaction instanceof ol.interaction.DragPan) {
			   inMap.removeInteraction(interaction);
		   }
		});
		
		var interaction = new ol.interaction.DragPan();
		inMap.addInteraction(interaction);
	},
	satFmbZoomIn : function(inMap) {
		
		SURVEYUTILS.unregisterMouseEvents(inMap,"singleclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"dblclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"pointermove");
		SURVEYUTILS.removeAllDrawInteractions(inMap);
		SURVEYUTILS.removeSelectInteractions(inMap);
		SURVEYUTILS.removeAllSnapInteractions(inMap);
		
		ILFS.interaction.on('boxend', function(evt) {
			var extent = evt.target.getGeometry().getExtent();
			inMap.getView().fit(extent, inMap.getSize());
		});
		inMap.addInteraction(ILFS.interaction);
	},
	satFmbZoomOut : function(inMap) {
		SURVEYUTILS.unregisterMouseEvents(inMap,"singleclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"dblclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"pointermove");
		SURVEYUTILS.removeAllDrawInteractions(inMap);
		SURVEYUTILS.removeSelectInteractions(inMap);
		SURVEYUTILS.removeAllSnapInteractions(inMap);
		
		ILFS.interaction.on('boxend', function(evt) {
			var currentZoom = inMap.getView().getZoom();
			inMap.getView().setZoom(currentZoom - 1);
		});
		inMap.addInteraction(ILFS.interaction);
	},
	satFmbMapPan : function(inMap) {
		SURVEYUTILS.unregisterMouseEvents(inMap,"singleclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"dblclick");
		SURVEYUTILS.unregisterMouseEvents(inMap,"pointermove");
		SURVEYUTILS.removeAllDrawInteractions(inMap);
		SURVEYUTILS.removeSelectInteractions(inMap);
		SURVEYUTILS.removeAllSnapInteractions(inMap);
		
		inMap.getInteractions().forEach(function (interaction) {
		   if (interaction instanceof ol.interaction.DragPan) {
			   inMap.removeInteraction(interaction);
		   }
		});
		var interaction = new ol.interaction.DragPan();
		inMap.addInteraction(interaction);
	},
	
	showPrintPdfMap : function (village_id,surveyNo,scale,dpi){
		
		if(scale != null){
			var jspcall = "downloadTonchMapPdf?village_id="+village_id+"&survey_number="+surveyNo+"&scale="+scale+"&dpi="+dpi;
		    window.open(jspcall, '_blank');	
		} else {
			var jspcall = "downloadTonchMapPdf?village_id="+village_id+"&survey_number="+surveyNo+"&scale=3960&dpi="+dpi;
		    window.open(jspcall, '_blank');	
		}
	},

	displayTipponMap : function () {
		let village_id = $("#village_id").val();
		let surveyNo = $("#surveyNoField").val();
		let dpi = getDPI();
		ILFS.checkForTipponMap(village_id, surveyNo);
	},
	showPrintPdfForTipponMap : function (village_id,surveyNo, dpi,transactionId , userId){
		var form = document.createElement("form");
	    form.setAttribute("method", "post");
	    form.setAttribute("action", "downloadTipponMapPdf");
	    var params = {villageId : village_id, surveyNumber: surveyNo, dpi: dpi, transactionId: transactionId, userId : userId};
	    for(var key in params) {
	        if(params.hasOwnProperty(key)) {
	            var hiddenField = document.createElement("input");
	            hiddenField.setAttribute("type", "hidden");
	            hiddenField.setAttribute("name", key);
	            hiddenField.setAttribute("value", params[key]);

	            form.appendChild(hiddenField);
	         }
	    }

	    document.body.appendChild(form);
	    form.target = "_blank"; 
	    form.submit()
	    document.body.removeChild(form); 
			/*var jspcall = "downloadTipponMapPdf?villageId="+village_id+"&surveyNumber="+surveyNo+"&dpi="+dpi+"&transactionId="+transactionId+"&userId="+userId;
		    window.open(jspcall, '_blank');	*/
	},
	checkForTipponMap : function (village_id, surveyNo){
		$.post(gisAppContextPath+"/restAPI/checkForTipponMap", 
				{
			      villageId : village_id,
			      surveyNo : surveyNo
			    },
			    function(response){
			    	if(response == "1" || response == "2"){
			    		dpi = getDPI();
			    		transactionId = transactionId;//getURLParamValue('transactionId');
			    		userId = userID;//getURLParamValue('userId');
			    		/*if(userId == null){
			    			userId = getURLParamValue('userID');
			    		}*/
			    		ILFS.showPrintPdfForTipponMap(village_id, surveyNo, dpi, projectId, userId);
			    	}else{
							bootbox.confirm({
							title:"Tippon Not Found",
			    			message: "<h5>Are you want to create using FMB Entry?</h5>",
			    		    buttons: {
			    		        confirm: {
			    		            label: 'Yes',
			    		            className: 'btn-success'
			    		        },
			    		        cancel: {
			    		            label: 'No',
			    		            className: 'btn-danger'
			    		        }
			    		    },
			    		    callback: function (result) {
			    		        if(result){
			    		        	let jscall =  gisAppContextPath+"/showfmbentry?villageId="+village_id+"&surveyNumber="+surveyNo;
								    window.open(jscall, '_self');
			    		        }
			    		    }
			    		});
			    	}
			    }
	    );
	},
	surveyPublicViewPahani: function(khataNo, survNo){
	   	 //debugger;
			var mandal = $("#mandal_id").val();   	 
	        var khata_id = khataNo;
	        //var survey_id=document.getElementById("surveyIdselect").value;
	        var survey_id = survNo;
	        
	        if(khata_id!='0'){
	       	 	document.getElementById("khataNumberPdf").value=khata_id; 
	        } else {
	       	 	document.getElementById("khataNumberPdf").value=survey_id;
	        }
	        document.getElementById("villageIdPdf").value=inVillageId;
	        document.getElementById("villageLl").value=villagellName.trim();
	        document.getElementById("districtLl").value=districtllName.trim();
	        document.getElementById("mandalLl").value=mandalllName.trim();
	   	 	document.getElementById("surveyNumberPdf").value = survNo;
			document.requestForm.action = pahaniCopy;
			document.requestForm.target = "_blank";
		    document.requestForm.submit();		
	},
	displaySurveyTipponPDF : function (villageId, surveyNumber) {
		let dpi = getDPI();
		ILFS.checkForTipponMap(villageId, surveyNumber);
	},
	getFMBSurveyMap : function(villageId, surveyId){
		if(villageId == ""){
			alertMessage(5764322, alert_vmnl);
			return false;
		}else if(surveyId == '' || surveyId == null || surveyId == 'surveyId'){ 
			alertMessage(5764322654, alert_noSNo);
			return false;
		}else {
			$("#info_message").show();
			document.getElementById('info_message').innerHTML = "<p><i class='fa fa-spin fa-spinner'></i> Loading...please wait...</p>";
			var formData = {};			
	    	formData = {
	    		villageCode : villageId,
	    		surveyNumber :  surveyId
	    	};
			var surveyMap = $.ajax({
				type : "POST",
				contentType : "application/json",
				url : "api/gis/getsurveyidfeature",
				data : JSON.stringify(formData),
				dataType : 'json',
				async : false,
				success : function(result) {
					if(result){
						//console.log(result);
						//bootbox.alert('At Survey Info Response ' + result);
					}
				},
				error : function(jqXHR, textStatus, errorThrown) {
					//bootbox.alert(jqXHR.status + ' ' + jqXHR.responseText);
					console.log("ERROR: ", jqXHR.responseText);
				}
			}).responseJSON;
		}
		var feat = JSON.parse(surveyMap[0].feat_json.value);
		if(feat.features != null){
			ILFS.displayFMBSurveyAttributeInfo(feat, villageId, surveyId);
		} else {
			alertMessage(alert_snne + " - " + surveyId);
			document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage"/>';
		}				
		return null;
	},
	displayFMBSurveyAttributeInfo : function (myJson, villageId, surveyId){
 	   
		var format = new ol.format.GeoJSON();
		var feature = format.readFeatures(myJson);
		csvFeatures = feature[0].getGeometry().getCoordinates();
		vectorSource_search.clear();
		vectorSource_search.addFeatures(feature);		
		vectorLayer_search.setStyle(ILFS.highlightStyle);
		vectorLayer_search.once('render', function() {
	        map.getView().fit(vectorLayer_search.getSource().getExtent(), map.getSize());
	        map.getView().setZoom(map.getView().getZoom()-1);	        
	    });
		
		var sInfo = ILFS.getVillageInfo(villageId, surveyId, displayPahaniDetails);
		//console.log(sInfo);
		var baseSyrveyNumber = null;
		if(sInfo.data.length != 0) {			
			if(sInfo.data.length === 1){
				baseSyrveyNumber = sInfo.data[0].survey_number;
			} else {
				baseSyrveyNumber = sInfo.data[0].base_survey_no;
			}
		}
		if(sInfo.data.length === 0 || sInfo.total_land_extent.length === 0){			
			alertMessage(12343222, alert_ndas + " - <b>" + surveyId);				
			$("#info_message").show();
			document.getElementById('info_message').innerHTML = '<spring:message code="info.parcelmessage" />';			
		} else {
			$("#info_message").hide();
    	    $("#location").empty();	        	          	    
    	    var trHTML = '';					
    	    trHTML += '<table lang="te" id="location" class="table table-sm table-small-font table-striped table-hover">';
    	    if(rsrextent === true){
    	    	trHTML += '<tr><td>సర్వే సంఖ్య </td><td colspan="3">మొత్తం RSR విస్తీర్ణం</td></tr>';
        	    trHTML += '<tr><td>'+sInfo.total_rsr_extent[0].surveyno+'</td><td colspan="3">'+sInfo.total_rsr_extent[0].rsrextent+'</td></tr>';
    	    }	        
    	    trHTML += '<tr><td>సర్వే సంఖ్య </td><td colspan="3">మొత్తం  విస్తీర్ణం</td></tr>';
    	    trHTML += '<tr><td>'+baseSyrveyNumber+'</td><td colspan="3">'+sInfo.total_land_extent[0].total_extent+'</td></tr>';
    	    trHTML += '<tr><td>సర్వే సంఖ్య / ఉప విభాగం </td><td colspan="3">విస్తీర్ణం </td></tr>';
	        $.each(sInfo.data, function (i, item) {
	        	if(displayPahaniDetails === false){
	        		trHTML += '<tr>';
	        	} else {
	        		trHTML += '<tr class="clickable" data-toggle="collapse" data-target="#expandSInfo'+[i]+'" >';
	        	}	        	
	        	trHTML += '<td>' + sInfo.data[i].survey_number + '</td>';
	        	trHTML += '<td>' + sInfo.data[i].total_extent_of_land + '</td>';
	        	//trHTML += '<td><i class="fa fa-plus text-success" style="color:blue"></i></td>';
	        	if(displayPahaniDetails === false){
	        		//trHTML += '<td><img style="width: 15px;" class="img-responsive" src="./img/view.png" id="viewPahani" data-toggle="tooltip" title="View Pahani" onclick="ILFS.surveyPublicViewPahani('+"'" + sInfo.data[i].khata_number + "'"+', '+"'" + sInfo.data[i].survey_number + "'"+')"/></td>';
	        	} else {
	        		//trHTML += '<td><img class="img-responsive" src="./img/view.png" id="viewPahani" data-toggle="tooltip" title="View Pahani" onclick="ILFS.surveyPublicViewPahani('+"'" + sInfo.data[i].khata_number + "'"+', '+"'" + sInfo.data[i].survey_number + "'"+')"/> &nbsp;&nbsp; <a data-toggle="collapse" data-target="#expandSInfo'+[i]+'" aria-expanded="false" aria-controls="menu"> <i class="fa fa-plus" style="color:blue"></i><i class="fa fa-minus" style="color:red"></i></a></td>';
	        	}	        	
	        	trHTML += '</tr>';
	   		        	
	        	trHTML += '<tr id="expandSInfo'+[i]+'" class="panel-collapse collapse out"><td width="100%" colspan="3">';
	        	trHTML += '<table class="table table-striped table-hover table-bordered table-dark tablebgcolor "><tr><td>పట్టాదారు పేరు </td>';
	        	trHTML += '<td>' + sInfo.data[i].pattadar_name + '</td></tr>'
	        	trHTML += '<tr><td>పట్టాదారు తండ్రి పేరు </td><td>' + sInfo.data[i].pattadat_father_name + '</td></tr>';
	        	trHTML += '<tr><td>అనుభవదారు పేరు  </td><td>' + sInfo.data[i].occupant_name + '</td></tr>';
	        	trHTML += '<tr><td>అనుభవదారు తండ్రి / భర్త  పేరు  </td><td>' + sInfo.data[i].occupant_father_name + '</td></tr>';
	        	trHTML += '<tr><td>అనుభవ విస్తీర్ణం  </td><td>' + sInfo.data[i].occupant_extent + '</td></tr>';
	        	trHTML += '<tr><td>సాగుకు పనికి వచ్చు విస్తీర్ణం </td><td>' + sInfo.data[i].cultiable_land + '</td></tr>';
	        	trHTML += '<tr><td>సాగుకు పనికి రాని విస్తీర్ణం </td><td>' + sInfo.data[i].uncultivated_land + '</td></tr>';
	        	trHTML += '<tr><td>భూమి స్వభావం </td><td>' + sInfo.data[i].land_nature_ll + '</td></tr>';
	        	trHTML += '<tr><td>భూమి వివరణ </td><td>' + sInfo.data[i].land_classification_ll + '</td></tr>';
	        	trHTML += '<tr><td>వ్యవసాయ విస్తరణ </td><td>' + sInfo.data[i].agri_extents + '</td></tr>';
	        	trHTML += '<tr><td>వ్యవసాయేతర విస్తరణ </td><td>' + sInfo.data[i].nonagri_extents + '</td></tr>';
	        	trHTML += '</table></td></tr>';			        	
	        	
	        });		        
	        $('#location').append(trHTML);
	        
	        if(ILFS.detectmob()){
	        	bootbox.alert({ 
	  	  		  size: "small",
	  	  		  message: trHTML, 
	  	  		  callback: function(){ /* your callback code */ }
	  	  		}).find('.modal-content').css({'font-size': '0.76555em', 'opacity': '0.75'} );
	        }	        
    	   
	        $('.fa-plus').on('click', function(){
	        	$(this).parent().find(".fa-plus").removeClass("fa-plus").addClass("fa-minus");
	        }).on('click', function(){
	        	$(this).parent().find(".fa-minus").removeClass("fa-minus").addClass("fa-plus");
	        });	
        
		}
	},
	
	viewTipponDocument : function (){
		let villageId = null;
		let surveyNo =  "%";
		try{
			villageId = $("#village_id").val();
			surveyNo = $("#surveyNoField").val();
			if(villageId == 0 ){
				alert('Please select village');
			} 
			else if(surveyNo == ''){
				alert('Please click on Survey No');
			}
		}catch{
			console.error("villageId / Survey No not found.....");
		}	
		try{
			if(villageId != 0  && surveyNo !== ''){
				getPublicDataForSerachBySurveyNo(villageId, surveyNo);
			}
		}catch{
			console.error("Tippon not found.....");
		}
	},
	publicViewEC: function(survNo){
	   	 	let vid = parseInt($("#village_id").val());
	   	  	document.getElementById("villageIdEC").value = vid; 
	   	 	document.getElementById("surveyNoEC").value = survNo;
			document.requestFormEC.action = ecCopy;
			document.requestFormEC.target = "_blank";
		    document.requestFormEC.submit();		
		},
		
	checkToleranceExtent: function(surveyDet){
			
			var jsonres='';
			 $.ajax({
		         type: "POST",
		         contentType : "application/json",
		         url : gisAppContextPath+"/restAPI/checktoleranceextent",
		 	     data: JSON.stringify(surveyDet),
		 		 async : false,
		 		 success : function(result) {
		 			if(result){
		 				jsonres=JSON.parse(result);
		 				return jsonres;
		 			}
		 		 },
		         failure: function (response) {console.log(response); },
		         error: function (response) {console.log(response); }
		     });
			 return jsonres;
		},
	createMsgBox: function(tolerancedata){
			var msgHTML = [];
			confirmdiv=$('<div></div>');
			table = $('<table border="1" cellpadding="6" cellspacing="5" style="display: block;border:1px orange;max-height:172px;overflow:auto; width:96%;"></table>');
			var body='<tbody style="color: #2F4F4F;"><tr>'+
			'<th style="font-size: 12.5px;background-color: #DAEEB6;">Survey/ Sub-Division No.</th>'+
			'<th style="font-size: 12.5px;background-color: #DAEEB6;">Extent as per Revenue Records <br>(Ac. Gts)</th>'+
			'<th style="font-size: 12.5px;background-color: #DAEEB6;">Extent as per Survey <br>(Ac. Gts)</th>'+
			'<th style="font-size: 13px;background-color: #DAEEB6;">Difference in Extent <br>(Ac. Gts)</th>'+
			'<th style="font-size: 12.5px;background-color: #DAEEB6;">Status</th>'+				
			'</tr></tbody>';
			tbody = $(body);
			var defaultmsg = "<p style='font-size: 12.5px;margin-top:3.5%;color:#2F4F4F'>There is mismatch found in the extent of the above Survey/Sub-Division No.<br/> Do you agree and continue with the mismatched extent?</p>";
			var toProceed=true;
			for (var i = 0; i < tolerancedata.length; i++) {
				  var object = eval(JSON.parse(tolerancedata[i]));
				  var tr= "<tr style='font-size: 12px;text-align:center'>";
				  var endtr="</tr>";
				  var td='',gap_value='',gap_percentage='',tolerance='',survey_tolerance_range='',status='',statusval='',statusbool='';
				   for (property in object) {
					   if(property=='statusval' || property=='gap_percentage' || property=='tolerance' || property=='survey_tolerance_range' || property=='status'){
						 //  if(property=='gap_value') gap_value=object[property];
						   if(property=='gap_percentage') gap_percentage=object[property];
						   if(property=='tolerance') tolerance=object[property];
						   if(property=='survey_tolerance_range') survey_tolerance_range=object[property];
						   if(property=='status') status=object[property];
						   if(property=='statusval'){
							   if(object[property]=='True') {statusval="./img/tickMark.jpg";statusbool=object[property];}
							   else {statusval="./img/close_red.png";statusbool=object[property];toProceed=false;}
						   }
					   }else{
						   td=td+"<td>"+object[property]+"</td>";
					   }
				   }
				   var title="<b class=title-bold>Details</b><hr><div style=text-align:left;><table border=1 cellpadding=6 cellspacing=5 style=border-color:#dee2e6ab;>"+
					  "<tr><td>Gap percentage</td><td> "+gap_percentage+"</td></tr><tr><td>Tolerance </td><td> "+tolerance+
					  "</td></tr><tr><td>Tolerance Range <td> "+survey_tolerance_range+"</td></tr><tr><td><span style=color:#dc3545;>Status </td><td> "+status+"</td></tr></span></table></div>";
				   
				   var imagetd="<td><img class='tolimg img-responsive' src="+statusval+" data-toggle='tooltip' data-html='true' data-placement='left'" +
				   		"data-original-title="+"'"+title+"'"+
				   		" title="+"'"+title+"'"+"/>" +
				   		"</td>";
				   tr=tr+td+imagetd+endtr;
				   tbody.append(tr);
			
			}
			table.append(tbody);
			confirmdiv.append(table);
			confirmdiv.append(defaultmsg);
			return [confirmdiv,toProceed];
		},
	 loadTooltip: function(){
		$(function() {
			 const $tooltip = $('[data-toggle="tooltip"]');
			 $tooltip.tooltip({		
				animation : true,
				html : true,
				placement : 'bottom',
				boundary: 'window',
				delay : {
					show : 1000,
					hide : 3000
				}
			});
			$tooltip.on('show.bs.tooltip', function()  {
				   $('.tooltip').not(this).remove();
				 });
			 
			$('[data-toggle="tooltip"]').on('mouseleave mouseout', function() {
				$('[data-toggle="tooltip"]').tooltip('hide');
			});
		});
	},

	assignSurveyNumberAfterPolygonize: function(){
		var surveyDet= ILFS.getSurveyExtentFromParcelInfo();
		var tolerancedata=ILFS.checkToleranceExtent(surveyDet);
		if(tolerancedata){
		var surveyPolygonFeatures = surveyPolyLayer.getSource().getFeatures();
		var isAreaMatched = true;
		var areaMismatchSurveyNos = new Array();
		var surveyExtent = [];
		$("#assignSurveyNumberTbl > tbody  > tr:gt(0)").each(function() {
			var rowIdStr = $(this).attr("id");
			var rowIdStrArr = rowIdStr.split("_");
			var rowId = rowIdStrArr[1];
			var polygonWKT = rowIdStrArr[2];
			var comboboxVal = $(this).find("select").children("option:selected").val();
			var polySurveyNumber = comboboxVal.split("@")[0];
			var subDivArea = comboboxVal.split("@")[1];
			var baseParcelNumber = comboboxVal.split("@")[2];
			
			surveyPolygonFeatures.forEach(function(feat){
				var formatWKT = new ol.format.WKT();
				var surveyPolygonWKT = formatWKT.writeGeometry(feat.getGeometry());
				var poltFeatArea = feat.getGeometry().getArea();
				var acreGunthas = getAcreGunthasFromSqmMeter(poltFeatArea);	
				
				if(surveyPolygonWKT === polygonWKT) {
					if(subDivArea != acreGunthas) {
						isAreaMatched = false;
						areaMismatchSurveyNos.push(polySurveyNumber);
						surveyExtent.push(polySurveyNumber, acreGunthas, subDivArea);
					}
				}
			});
	    });
		
		if(!isAreaMatched) {	
			var values=ILFS.createMsgBox(tolerancedata);
			var confirmdiv=values[0];
			var toProceed=values[1];
			console.log("toProceed-"+toProceed);
			$.msgbox({
				type: 'confirm',
				content: confirmdiv,
				title: "Confirm",
				initialHeight : 309,
				initialWidth : 562,
//				id: 9999888770089883,
				onOpen : function () {
					ILFS.loadTooltip();
					 $('.jMsgbox-button-1').attr("disabled", !toProceed);
				},
				onClose: function(){
					if(this.val() === true) {
						ILFS.assignSelectedSurveyNumbers();
					} else {
						return false;
					}				
				},
		});
			}
		else {
			ILFS.assignSelectedSurveyNumbers();
		}
		}
	},
	
	assignSelectedSurveyNumbers: function() {
	var surveyPolygonFeatures = surveyPolyLayer.getSource().getFeatures();
	$("#assignSurveyNumberTbl > tbody  > tr:gt(0)").each(function() {
		var rowIdStr = $(this).attr("id");
		var rowIdStrArr = rowIdStr.split("_");
		var rowId = rowIdStrArr[1];
		var polygonWKT = rowIdStrArr[2];
		var comboboxVal = $(this).find("select").children("option:selected").val();
		var polySurveyNumber = comboboxVal.split("@")[0];
		var subDivArea = comboboxVal.split("@")[1];
		var baseParcelNumber = comboboxVal.split("@")[2];
		
		surveyPolygonFeatures.forEach(function(feat){
			var formatWKT = new ol.format.WKT();
			var surveyPolygonWKT = formatWKT.writeGeometry(feat.getGeometry());
			var poltFeatArea = feat.getGeometry().getArea();
			var acreGunthas = getAcreGunthasFromSqmMeter(poltFeatArea);
			
			if(surveyPolygonWKT === polygonWKT) {
				feat.set("surveyNumber",polySurveyNumber);
				feat.set("oldBaseSurveyNumber",baseParcelNumber);
			}
		});
    });
	$('#assignSurveyNumberDiv').dialog('close');
},
 getSurveyExtentFromParcelInfo: function(){
	var surveyPolygonFeatures = surveyPolyLayer.getSource().getFeatures();
	var isAreaMatched = true;
	var areaMismatchSurveyNos = new Array();
	var surveyExtent = [];
	 var surveyDetails = [];
	$("#assignSurveyNumberTbl > tbody  > tr:gt(0)").each(function() {
		var rowIdStr = $(this).attr("id");
		var rowIdStrArr = rowIdStr.split("_");
		var rowId = rowIdStrArr[1];
		var polygonWKT = rowIdStrArr[2];
		var comboboxVal = $(this).find("select").children("option:selected").val();
		var polySurveyNumber = comboboxVal.split("@")[0];
		var subDivArea = comboboxVal.split("@")[1];
		var baseParcelNumber = comboboxVal.split("@")[2];
		
		surveyPolygonFeatures.forEach(function(feat){
			var formatWKT = new ol.format.WKT();
			var surveyPolygonWKT = formatWKT.writeGeometry(feat.getGeometry());
			var poltFeatArea = feat.getGeometry().getArea();
			var acreGunthas = getAcreGunthasFromSqmMeter(poltFeatArea);	
			
			if(surveyPolygonWKT === polygonWKT) {
				if(subDivArea != acreGunthas) {
					isAreaMatched = false;
					areaMismatchSurveyNos.push(polySurveyNumber);
					surveyExtent.push(polySurveyNumber, acreGunthas, subDivArea);
				}
			}
		});
    });
	
	if(!isAreaMatched) {
		//var errorPolySurveyNos = areaMismatchSurveyNos.join(",");	
		var msgHTML = [];
		
		for(var i = 0; i < surveySubDivisionInfo.length; i++)
		{
			for(var x = 0; x < surveyExtent.length; x++){
				if(surveySubDivisionInfo[i].new_survey_number === surveyExtent[x]){
					var extent=surveySubDivisionInfo[i].extent;
					var surveyextent=surveyExtent[x+1];
					var diff=(surveySubDivisionInfo[i].extent - surveyExtent[x+1]).toFixed(4);
					if(extent==undefined || isNaN(extent)) extent='';
					if(surveyextent==undefined || isNaN(surveyextent)) surveyextent='';
					if(diff==undefined || isNaN(diff)) diff='';
					surveyDetails.push({surveynumber: surveySubDivisionInfo[i].new_survey_number, survey_extent: surveyextent ,revenue_extent:extent});
				}
			}
		}
	}
	return surveyDetails;
}
}

$('#CloseGIS').click(function(){
//	var isCsrf = updateToken();
	var tnsr= '';
	var allcookies = document.cookie;
	cookiearray = allcookies.split(';');
	for(var i=0; i<cookiearray.length; i++){
	 name = cookiearray[i].split('=')[0].trim();
	 value = cookiearray[i].split('=')[1].trim();
	 if(name == 'setAuth'){
	tnsr= value;
	 }
	} 
	//alert("CSRF-->"+tnsr);
	window.location.href ="callRevenueCitizenDashboard?csrf="+tnsr;	
	//window.location.href ="citizenDashboard?csrf="+isCsrf;		
});

