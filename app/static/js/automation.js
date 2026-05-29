(function () {
  if (!window.cnAgentOS) window.cnAgentOS = {};
  if (window.cnAgentOS.automation) return;
  window.cnAgentOS.automation = {};

  var MOD = window.cnAgentOS.automation;

  function getXsrf() {
    var match = document.cookie.match(/_xsrf=([^;]+)/);
    return match ? match[1] : '';
  }

  function postData(url, data, callback) {
    var fd = new FormData();
    Object.keys(data).forEach(function (k) { fd.append(k, data[k]); });
    fd.append('_xsrf', getXsrf());
    fetch(url, { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (data) { callback(data); })
      .catch(function (e) { alert('请求失败: ' + e.message); });
  }

  function readFields(prefix) {
    return {
      name: document.getElementById(prefix + 'Name').value,
      minute: document.getElementById(prefix + 'Minute').value || '*',
      hour: document.getElementById(prefix + 'Hour').value || '*',
      day: document.getElementById(prefix + 'Day').value || '*',
      month: document.getElementById(prefix + 'Month').value || '*',
      week: document.getElementById(prefix + 'Week').value || '*',
      keyword: document.getElementById(prefix + 'Keyword').value || '人工智能',
      item_count: document.getElementById(prefix + 'ItemCount').value || 10,
      max_pages: document.getElementById(prefix + 'MaxPages').value || 1,
    };
  }

  MOD.createJob = function () {
    var fields = readFields('create');
    if (!fields.name.trim()) { alert('请输入任务名称'); return; }
    postData('/admin/automation/create', fields, function (data) {
      if (data.ok) { location.reload(); }
      else { alert('创建失败: ' + (data.error || '未知错误')); }
    });
  };

  MOD.updateJob = function (jobId) {
    var fields = readFields('edit');
    if (!fields.name.trim()) { alert('请输入任务名称'); return; }
    postData('/admin/automation/update/' + jobId, fields, function (data) {
      if (data.ok) { location.reload(); }
      else { alert('更新失败: ' + (data.error || '未知错误')); }
    });
  };

  MOD.deleteJob = function (jobId, jobName) {
    if (!confirm('确认删除任务「' + jobName + '」？')) return;
    postData('/admin/automation/delete/' + jobId, {}, function (data) {
      if (data.ok) { location.reload(); }
      else { alert('删除失败: ' + (data.error || '未知错误')); }
    });
  };

  MOD.toggleJob = function (jobId) {
    postData('/admin/automation/toggle/' + jobId, {}, function (data) {
      if (data.ok) { location.reload(); }
      else { alert('操作失败: ' + (data.error || '未知错误')); }
    });
  };

  MOD.runJob = function (jobId) {
    postData('/admin/automation/run/' + jobId, {}, function (data) {
      if (data.ok) {
        alert('手动执行成功: ' + (data.message || ''));
        location.reload();
      } else {
        alert('执行失败: ' + (data.error || '未知错误'));
      }
    });
  };

  MOD.openCreateModal = function () {
    var el = document.getElementById('createModal');
    if (el) {
      var bsModal = new bootstrap.Modal(el);
      bsModal.show();
    }
  };

  MOD.openEditModal = function (jobId, name, cron, config) {
    var el = document.getElementById('editModal');
    if (!el) return;
    var parts = cron.split(' ');
    document.getElementById('editJobId').value = jobId;
    document.getElementById('editName').value = name;
    document.getElementById('editMinute').value = parts[0] || '*';
    document.getElementById('editHour').value = parts[1] || '*';
    document.getElementById('editDay').value = parts[2] || '*';
    document.getElementById('editMonth').value = parts[3] || '*';
    document.getElementById('editWeek').value = parts[4] || '*';
    try {
      var cfg = JSON.parse(config);
      document.getElementById('editKeyword').value = cfg.keyword || '人工智能';
      document.getElementById('editItemCount').value = cfg.item_count || 10;
      document.getElementById('editMaxPages').value = cfg.max_pages || 1;
    } catch (e) {
      document.getElementById('editKeyword').value = '人工智能';
      document.getElementById('editItemCount').value = 10;
      document.getElementById('editMaxPages').value = 1;
    }
    var bsModal = new bootstrap.Modal(el);
    bsModal.show();
  };

  MOD.previewCron = function (prefix) {
    var m = document.getElementById(prefix + 'Minute').value || '*';
    var h = document.getElementById(prefix + 'Hour').value || '*';
    var d = document.getElementById(prefix + 'Day').value || '*';
    var mo = document.getElementById(prefix + 'Month').value || '*';
    var w = document.getElementById(prefix + 'Week').value || '*';
    var expr = m + ' ' + h + ' ' + d + ' ' + mo + ' ' + w;
    var el = document.getElementById(prefix + 'Preview');
    if (!el) return;
    el.textContent = 'Cron 表达式: ' + expr;
    el.style.transition = 'none';
    el.style.color = '#10b981';
    el.style.fontWeight = 'bold';
    setTimeout(function () {
      el.style.transition = 'color 0.8s, font-weight 0.8s';
      el.style.color = '';
      el.style.fontWeight = '';
    }, 50);
  };

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelector('.table-responsive table tbody').addEventListener('click', function (e) {
      var btn = e.target.closest('button');
      if (!btn) return;
      var row = btn.closest('tr');
      if (!row) return;

      var jobId = parseInt(row.getAttribute('data-job-id'));
      var jobName = row.getAttribute('data-job-name') || '';
      var jobCron = row.getAttribute('data-job-cron') || '';
      var jobConfig = row.getAttribute('data-job-config') || '{}';

      if (btn.classList.contains('btn-run-job')) {
        MOD.runJob(jobId);
      } else if (btn.classList.contains('btn-toggle-job')) {
        MOD.toggleJob(jobId);
      } else if (btn.classList.contains('btn-edit-job')) {
        MOD.openEditModal(jobId, jobName, jobCron, jobConfig);
      } else if (btn.classList.contains('btn-delete-job')) {
        MOD.deleteJob(jobId, jobName);
      }
    });
  });
})();
