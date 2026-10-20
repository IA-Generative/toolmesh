import { forwardRef } from "react";
import { Link as RouterLink } from "react-router";

export const Link = forwardRef(function Link({ href, ...rest }, ref) {
  return <RouterLink ref={ref} to={href} {...rest} />;
});
