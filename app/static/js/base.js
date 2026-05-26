/**
 * 成员 A：门户与认证页通用脚本
 */
(function () {
    "use strict";

    window.cnAgentOS = window.cnAgentOS || {};

    cnAgentOS.validatePassword = function (password) {
        if (!password || password.length < 6 || password.length > 32) {
            return "密码长度需为 6～32 位";
        }
        if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
            return "密码需同时包含字母和数字";
        }
        return null;
    };

    cnAgentOS.validateUsername = function (username) {
        if (!username) {
            return "用户名不能为空";
        }
        if (!/^[A-Za-z0-9_]{3,20}$/.test(username)) {
            return "用户名需为 3～20 位字母、数字或下划线";
        }
        return null;
    };
})();
