// Lightweight Odometer / Number Animator
window.Odometer = window.Odometer || function(opts) {
  this.el = opts.el;
  this.value = opts.value || 0;
  this.update = function(newVal) {
    this.value = newVal;
    if (this.el) {
      this.el.innerText = '₹' + Number(newVal).toLocaleString('en-IN');
    }
  };
};
