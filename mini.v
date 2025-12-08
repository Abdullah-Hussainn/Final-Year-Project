module chip_top(
  input        clk,
  input        rst_n,
  input  [7:0] gpio_in,
  output [7:0] gpio_out
);
  assign gpio_out = gpio_in;
endmodule
