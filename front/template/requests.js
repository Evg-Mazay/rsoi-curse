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
            document.location.href = "/"
       }
    })
}


function sign_out(){

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
       success: function(jsondata){
            console.log("Token obtained: " + jsondata["auth_token"]);
            document.cookie = "token=" + jsondata["auth_token"];
            document.cookie = "user=" + login;
            document.location.href = "/"
       }
    })
}


function make_book(office_start, office_end, car_uuid, time_start, time_end, cc_num, sum){
    $.ajax({
       type: 'POST',
       crossDomain: true,
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
       }
    })
}