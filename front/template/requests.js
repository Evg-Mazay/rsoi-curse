function error_function(jqXHR, exception){
    $( "#error_message_alert" ).text("[" + jqXHR.status + "] " + jqXHR.responseText);
    $( "#error_message_alert" ).show();
}

function success_function(data){
    $( "#success_message_alert" ).text(data);
    $( "#success_message_alert" ).show();
}

function sign_in(login, password){
    $.ajax({
       type: 'POST',
       crossDomain: true,
       withCredentials: true,
       dataType: 'json',
       data: JSON.stringify({"login": login, "password": password}),
       url: '{{ sign_in_endpoint }}',
       contentType: 'application/json',
       success: function(jsondata){
            console.log("Token obtained: " + jsondata["auth_token"]);
            document.cookie = "token=" + jsondata["auth_token"];
            document.cookie = "user=" + login;
            document.cookie = "is_admin=" + jsondata["is_admin"];
            document.location.href = "/"
       },
       error: error_function
    })
}


function sign_out(){
    document.cookie = "token= ; expires = Thu, 01 Jan 1970 00:00:00 GMT";
    document.cookie = "user= ; expires = Thu, 01 Jan 1970 00:00:00 GMT";
    document.cookie = "is_admin= ; expires = Thu, 01 Jan 1970 00:00:00 GMT";
    document.location.href = "/";
}


function register(login, password){
    $.ajax({
       type: 'POST',
       crossDomain: true,
       withCredentials: true,
       dataType: 'json',
       data: JSON.stringify({"login": login, "password": password}),
       url: '{{ register_endpoint }}',
       contentType: 'application/json',
       success: success_function,
       error: error_function
    })
}


function make_book(office_start, office_end, car_uuid, time_start, time_end, cc_num, sum){
    $.ajax({
       type: 'POST',
       crossDomain: true,
       withCredentials: true,
       xhrFields: {withCredentials: true},
       dataType: 'json',
       data: JSON.stringify({
            "car_uuid": car_uuid,
            "user_id": 0,
            "payment_data": {
                "cc_number": cc_num,
                "price": sum,
            },
            "booking_start": time_start,
            "booking_end": time_end,
            "start_office": office_start,
            "end_office": office_end,
       }),
       url: '{{ book_endpoint }}',
       contentType: 'application/json',
       success: function(jsondata){
            document.location.href = "/";
       },
       error: error_function
    })
}


function cancel_book(booking_id){
    $.ajax({
       type: 'DELETE',
       crossDomain: true,
       xhrFields: {withCredentials: true},
       url: '{{ book_endpoint }}/' + booking_id,
       success: function(jsondata){
            document.location.href = "/";
       },
       error: error_function
    })
}


function end_book(booking_id){
    $.ajax({
       type: 'PATCH',
       crossDomain: true,
       xhrFields: {withCredentials: true},
       url: '{{ book_endpoint }}/' + booking_id + "/finish",
       success: function(jsondata){
            document.location.href = "/";
       },
       error: error_function
    })
}

function delete_car_completely(car_uuid) {
    $.ajax({
       type: 'DELETE',
       crossDomain: true,
       xhrFields: {withCredentials: true},
       url: '{{ offices_endpoint }}/cars/' + car_uuid + '/completely',
       success: function(jsondata){
            document.location.href = "/";
       },
       error: error_function
    })
}


function add_office(location) {
    $.ajax({
       type: 'POST',
       crossDomain: true,
       xhrFields: {withCredentials: true},
       contentType: 'application/json',
       data: JSON.stringify({"location": location}),
       url: '{{ offices_endpoint }}',
       success: function(jsondata){
            document.location.href = "/";
       },
       error: error_function
    })
}

function add_car(office_id, car_uuid, available_from) {
    $.ajax({
       type: 'POST',
       crossDomain: true,
       xhrFields: {withCredentials: true},
       contentType: 'application/json',
       data: JSON.stringify({"available_from": available_from}),
       url: '{{ offices_endpoint }}/' + office_id + '/cars/' + car_uuid,
       success: function(jsondata){
            document.location.href = "/";
       },
       error: error_function
    })
}


function create_car(brand, model, type, power) {
    $.ajax({
       type: 'POST',
       crossDomain: true,
       xhrFields: {withCredentials: true},
       contentType: 'application/json',
       data: JSON.stringify({"brand": brand, "model": model, "type": type, "power": power}),
       url: '{{ cars_list_endpoint }}',
       success: function(jsondata){
            document.location.href = "/";
       },
       error: error_function
    })
}